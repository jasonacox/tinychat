"""RLM (Recursive Language Models) service for code execution capabilities."""

import asyncio
import json
import logging
import queue
import re
import threading
import time
import traceback
from typing import AsyncGenerator, Dict, List

from app.config import Settings

logger = logging.getLogger("tinychat")

# Check if RLM is available
if Settings.HAS_RLM:
    from rlm import RLM
    from rlm.utils.parsing import find_final_answer, format_iteration
    from rlm.utils.prompts import build_user_prompt


class RLMService:
    """Service for RLM-powered chat with code execution."""
    
    @staticmethod
    async def stream_rlm_completion(
        messages: List[Dict],
        model: str,
        show_thinking: bool = True,
        document_context: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream RLM completion with code execution.
        
        Args:
            messages: Conversation history
            model: LLM model to use
            show_thinking: Whether to stream the thinking process
            document_context: Optional document content to include in context
            
        Yields:
            SSE-formatted data chunks
        """
        if not Settings.HAS_RLM:
            yield f"data: {json.dumps({'error': 'RLM module not installed'})}\n\n"
            return
        
        logger.info(f"RLM generation request for model: {model}")
        
        # Always send a startup indicator
        if show_thinking:
            thinking_msg = json.dumps({'content': '> [RLM Startup...]\n\n'})
            yield f"data: {thinking_msg}\n\n"
        else:
            thinking_msg = json.dumps({'content': '🧠 *RLM is thinking...*\n\n'})
            yield f"data: {thinking_msg}\n\n"
        
        # Prepare RLM
        rlm_inst = RLM(
            backend="openai",
            backend_kwargs={
                "model_name": model,
                "api_key": Settings.OPENAI_API_KEY,
                "base_url": Settings.OPENAI_API_URL,
            },
            verbose=False,
        )
        
        # Build query with document context if provided
        user_prompt = messages[-1]["content"] if messages else ""
        
        if document_context:
            rlm_query = f"""Consider the context below, and answer the prompt:

<CONTEXT>
{document_context}
</CONTEXT>

PROMPT:
{user_prompt}"""
        else:
            rlm_query = user_prompt
        
        message_queue = queue.Queue()  # Thread-safe queue
        thread_done = threading.Event()
        cancellation_requested = threading.Event()
        start_time = time.time()
        
        def rlm_worker(show_thinking_mode):
            try:
                with rlm_inst._spawn_completion_context(rlm_query) as (lm_handler, environment):
                    message_history = rlm_inst._setup_prompt(rlm_query)
                    for i in range(rlm_inst.max_iterations):
                        # Check for cancellation
                        if cancellation_requested.is_set():
                            message_queue.put({
                                "type": "error", 
                                "content": f"RLM execution cancelled (timeout: {Settings.RLM_TIMEOUT}s)"
                            })
                            return
                        
                        # Check timeout
                        if time.time() - start_time > Settings.RLM_TIMEOUT:
                            message_queue.put({
                                "type": "error", 
                                "content": f"RLM timeout after {Settings.RLM_TIMEOUT}s"
                            })
                            return
                        
                        # Determine counts
                        context_count = 1
                        if hasattr(environment, "get_context_count"):
                            context_count = environment.get_context_count()
                        
                        history_count = 0
                        if hasattr(environment, "get_history_count"):
                            history_count = environment.get_history_count()
                        
                        current_prompt = message_history + [
                            build_user_prompt(None, i, context_count, history_count)
                        ]
                        
                        # Send status
                        if show_thinking_mode:
                            message_queue.put({
                                "type": "status",
                                "content": f"\n\n---\n#### 🧠 Iteration {i+1} Thinking\n"
                            })
                        else:
                            message_queue.put({
                                "type": "brief_status",
                                "content": f"Iteration {i+1}..."
                            })
                        
                        iteration = rlm_inst._completion_turn(
                            prompt=current_prompt,
                            lm_handler=lm_handler,
                            environment=environment,
                        )
                        
                        # Format reasoning
                        reasoning_styled = iteration.response.replace('\n', '\n> ')
                        
                        # Gather execution outputs
                        execution_outputs = ""
                        for cb in iteration.code_blocks:
                            if cb.result.stdout:
                                execution_outputs += cb.result.stdout + "\n"
                        
                        # Resolve variables in reasoning
                        def _resolve_val(val_str):
                            v = val_str.strip().strip('"').strip("'")
                            if v.isidentifier():
                                if hasattr(environment, 'locals') and v in environment.locals:
                                    return str(environment.locals[v])
                                elif hasattr(environment, 'execute_code'):
                                    cr = environment.execute_code(f"print({v})")
                                    if not cr.stderr:
                                        return cr.stdout.strip()
                            return v
                        
                        reasoning_styled = re.sub(
                            r'FINAL(?:_VAR)?\((.*?)\)',
                            lambda m: f"**{_resolve_val(m.group(1))}**",
                            reasoning_styled
                        )
                        
                        update = f"\n> **Reasoning:**\n> {reasoning_styled}\n"
                        for cb in iteration.code_blocks:
                            if cb.code.strip():
                                code_styled = cb.code.replace('\n', '\n> ')
                                stdout_styled = str(cb.result.stdout).replace('\n', '\n> ') if cb.result.stdout else ''
                                
                                # Smart output capture
                                if not stdout_styled and not cb.result.stderr:
                                    try:
                                        lines = [l for l in cb.code.strip().split('\n') if l.strip()]
                                        if lines:
                                            last_line = lines[-1].strip()
                                            if '=' in last_line and not any(
                                                last_line.startswith(p) for p in ['if ', 'for ', 'while ', 'def ', 'class ']
                                            ):
                                                part = last_line.split('=')[0].strip()
                                                var_name = part.split(':')[-1].strip() if ':' in part else part
                                                if var_name.isidentifier():
                                                    val = _resolve_val(var_name)
                                                    if val != var_name:
                                                        stdout_styled = f"[Variable {var_name} = {val}]"
                                            elif last_line.isidentifier():
                                                val = _resolve_val(last_line)
                                                if val != last_line:
                                                    stdout_styled = f"[Value = {val}]"
                                    except Exception as e:
                                        logger.debug(f"Error resolving variable value: {e}")
                                
                                if not stdout_styled:
                                    stdout_styled = '[No Output]'
                                
                                update += f"\n> **REPL Code:**\n> ```python\n> {code_styled}\n> ```\n"
                                update += f"> **Result:**\n> ```\n> {stdout_styled}\n> ```\n"
                        
                        message_queue.put({"type": "update", "content": update})
                        
                        final_answer = find_final_answer(iteration.response, environment=environment)
                        
                        # Fallback for final answer
                        if final_answer is None and (
                            "final answer" in iteration.response.lower() or 
                            "completed" in iteration.response.lower()
                        ):
                            if execution_outputs.strip():
                                final_answer = execution_outputs.strip()
                            else:
                                final_answer = iteration.response
                        
                        if final_answer is not None:
                            # Clean up final answer
                            if isinstance(final_answer, str):
                                final_answer = final_answer.strip().strip('"').strip("'")
                                
                                # Smart variable resolution
                                if final_answer.isidentifier():
                                    if hasattr(environment, 'locals') and final_answer in environment.locals:
                                        final_answer = str(environment.locals[final_answer])
                                    elif hasattr(environment, 'execute_code'):
                                        check_res = environment.execute_code(f"print({final_answer})")
                                        if not check_res.stderr:
                                            final_answer = check_res.stdout.strip()
                            
                            message_queue.put({"type": "final", "content": final_answer})
                            return
                        
                        # Format for next turn
                        message_history.extend(format_iteration(iteration))
            except Exception as e:
                logger.error(f"RLM Worker Exception: {str(e)}\n{traceback.format_exc()}")
                message_queue.put({"type": "error", "content": f"RLM Worker Error: {str(e)}"})
            finally:
                thread_done.set()
        
        # Start worker thread
        worker_thread = threading.Thread(target=rlm_worker, args=(show_thinking,), daemon=True)
        worker_thread.start()
        
        assistant_full_content = ""
        
        # Process messages with timeout
        while not thread_done.is_set() or not message_queue.empty():
            try:
                msg = message_queue.get(timeout=0.1)
                if msg["type"] in ["status", "update"]:
                    if show_thinking:
                        yield f"data: {json.dumps({'content': msg['content']})}\n\n"
                        assistant_full_content += msg['content']
                elif msg["type"] == "brief_status":
                    yield f"data: {json.dumps({'rlm_status': msg['content']})}\n\n"
                elif msg["type"] == "final":
                    final_msg = msg['content']
                    if show_thinking:
                        final_answer_header = f"\n\n---\n### ✅ Final Answer\n\n"
                        yield f"data: {json.dumps({'content': final_answer_header + final_msg})}\n\n"
                        assistant_full_content += final_answer_header + final_msg
                    else:
                        yield f"data: {json.dumps({'content': final_msg})}\n\n"
                        assistant_full_content += final_msg
                elif msg["type"] == "error":
                    yield f"data: {json.dumps({'error': msg['content']})}\n\n"
            except queue.Empty:
                # Check for timeout
                if time.time() - start_time > Settings.RLM_TIMEOUT:
                    if not cancellation_requested.is_set():
                        cancellation_requested.set()
                        logger.warning(f"RLM timeout detected after {Settings.RLM_TIMEOUT}s")
                    if not thread_done.is_set():
                        await asyncio.sleep(0.5)
                    yield f"data: {json.dumps({'error': f'RLM execution timeout ({Settings.RLM_TIMEOUT}s)'})}\n\n"
                    break
                await asyncio.sleep(0.1)
