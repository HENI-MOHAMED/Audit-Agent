from langchain_core.messages import ToolMessage
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.utils.stream_utils import get_emitter

def _execute_tool_calls_parallel(tool_calls: list, tool_map: dict, agent_name: str = "agent", state: dict = None) -> list[ToolMessage]:
    """Execute multiple tool calls in parallel using threads. Falls back to sequential for single calls."""
    emitter = get_emitter()
    
    def _prepare_args(tc):
        args = dict(tc["args"])
        # Some tools might require state injected if we call them manually here
        tool_fn = tool_map.get(tc["name"])
        if tool_fn and state is not None:
             # Basic check if tool accepts state/state annotation
             # LangChain's InjectedState tools usually expect it if passed or fail if missing
             # We can let ToolNode mechanics handle it if possible, but for tools requiring it we inject:
             args["state"] = state
        return args

    if len(tool_calls) == 1:
        tc = tool_calls[0]
        if emitter: emitter.emit_agent_tool_call(agent_name, tc["name"], tc["args"])
        tool_fn = tool_map.get(tc["name"])
        if tool_fn is None:
            err = f"Error: Unknown tool '{tc['name']}'"
            if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], err)
            return [ToolMessage(content=err, name=tc["name"], tool_call_id=tc["id"])]
        
        args = tc["args"]
        if hasattr(tool_fn, 'args_schema') and tool_fn.args_schema:
             if 'state' in tool_fn.args_schema.schema().get('properties', {}) and state is not None:
                 args = dict(args)
                 args['state'] = state
                 
        try:
            result = tool_fn.invoke(args)
        except Exception as e:
            err_msg = f"Error invoking tool '{tc['name']}': {str(e)}"
            if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], err_msg)
            return [ToolMessage(content=err_msg, name=tc["name"], tool_call_id=tc["id"])]
            
        if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], str(result))
        return [ToolMessage(content=str(result), name=tc["name"], tool_call_id=tc["id"])]

    results = {}
    def _run(tc):
        if emitter: emitter.emit_agent_tool_call(agent_name, tc["name"], tc["args"])
        tool_fn = tool_map.get(tc["name"])
        if tool_fn is None:
            err = f"Error: Unknown tool '{tc['name']}'"
            if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], err)
            return tc["id"], tc["name"], err
            
        args = tc["args"]
        if hasattr(tool_fn, 'args_schema') and tool_fn.args_schema:
             if 'state' in tool_fn.args_schema.schema().get('properties', {}) and state is not None:
                 args = dict(args)
                 args['state'] = state
        
        try:
            res = str(tool_fn.invoke(args))
        except Exception as e:
            err_msg = f"Error invoking tool '{tc['name']}': {str(e)}"
            if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], err_msg)
            return tc["id"], tc["name"], err_msg
            
        if emitter: emitter.emit_agent_tool_result(agent_name, tc["name"], res)
        return tc["id"], tc["name"], res

    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 4)) as executor:
        futures = {executor.submit(_run, tc): tc for tc in tool_calls}
        for future in as_completed(futures):
            tc_id, name, content = future.result()
            results[tc_id] = (name, content)

    # Return in original order
    return [ToolMessage(content=results[tc["id"]][1], name=results[tc["id"]][0], tool_call_id=tc["id"]) for tc in tool_calls]
