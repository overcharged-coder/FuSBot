from economy_shared import state, save_state
import asyncio
import traceback
import math
import random
import statistics
import itertools
import tempfile
import os


def sandbox_exec(code: str) -> str:
    allowed_builtins = {
        "print": print, "range": range, "len": len, "int": int, "float": float,
        "str": str, "bool": bool, "abs": abs, "min": min, "max": max, "sum": sum,
        "math": math, "random": random, "statistics": statistics,
        "stats": statistics, "itertools": itertools,
    }
    env = {"__builtins__": allowed_builtins}
    output = []

    def fake_print(*args):
        output.append(" ".join(str(a) for a in args))

    env["print"] = fake_print
    try:
        exec(code, env, env)
    except Exception as e:
        output.append("Error: " + str(e))
        output.append(traceback.format_exc())
    return "\n".join(output)


async def run_cpp(code: str) -> str:
    tmpdir = tempfile.mkdtemp(prefix="codepad_cpp_")
    src_path = os.path.join(tmpdir, "main.cpp")
    bin_path = os.path.join(tmpdir, "main.out")
    try:
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            proc = await asyncio.create_subprocess_exec(
                "g++", src_path, "-O2", "-std=c++17", "-o", bin_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return "g++ not found."
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        except asyncio.TimeoutError:
            proc.kill(); return "Compilation timed out."
        if proc.returncode != 0:
            return "Compilation failed:\n" + stderr.decode(errors="ignore")
        try:
            run_proc = await asyncio.create_subprocess_exec(
                bin_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return "Binary missing."
        try:
            rstdout, rstderr = await asyncio.wait_for(run_proc.communicate(), timeout=3)
        except asyncio.TimeoutError:
            run_proc.kill(); return "Execution timed out."
        out = rstdout.decode(errors="ignore") + ("\n" + rstderr.decode(errors="ignore") if rstderr else "")
        return out.strip() or "(no output)"
    finally:
        for p in (src_path, bin_path):
            try: os.remove(p)
            except Exception: pass
        try: os.rmdir(tmpdir)
        except Exception: pass


def _get_pad(uid: str) -> dict:
    uid = str(uid)
    state.setdefault("codepad", {})
    if uid not in state["codepad"]:
        state["codepad"][uid] = {}
        save_state()
    pad = state["codepad"][uid]
    normalized = {}
    changed = False
    for fn, val in pad.items():
        if isinstance(val, str):
            normalized[fn] = val
        elif isinstance(val, dict) and isinstance(val.get("content"), str):
            normalized[fn] = val["content"]
            changed = True
        else:
            changed = True
    if changed:
        state["codepad"][uid] = normalized
        save_state()
    return normalized


async def setup(app):

    @app.command("/code_new")
    async def code_new(ack, command, respond):
        await ack()
        uid = command["user_id"]
        filename = (command.get("text") or "").strip()
        if not filename:
            return await respond(text="Usage: `/code_new <filename>`", response_type="ephemeral")
        pad = _get_pad(uid)
        if filename in pad:
            return await respond(text=":x: File already exists.", response_type="ephemeral")
        pad[filename] = ""
        save_state()
        await respond(text=f":page_facing_up: Created *{filename}*.")

    @app.command("/code_edit")
    async def code_edit(ack, command, client, body, respond):
        await ack()
        uid = command["user_id"]
        filename = (command.get("text") or "").strip()
        if not filename:
            return await respond(text="Usage: `/code_edit <filename>`", response_type="ephemeral")
        pad = _get_pad(uid)
        if filename not in pad:
            return await respond(text=":x: File does not exist.", response_type="ephemeral")
        current = pad[filename] or ""
        await client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "code_edit_modal",
                "title": {"type": "plain_text", "text": "Edit Code"},
                "submit": {"type": "plain_text", "text": "Save"},
                "private_metadata": uid + "|" + filename,
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "code_block",
                        "label": {"type": "plain_text", "text": filename},
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "code_input",
                            "multiline": True,
                            "initial_value": current[:3000],
                        },
                    }
                ],
            },
        )

    @app.view("code_edit_modal")
    async def code_edit_modal(ack, body, client):
        await ack()
        meta = body["view"].get("private_metadata", "")
        parts = meta.split("|", 1)
        if len(parts) != 2:
            return
        uid, filename = parts
        new_code = body["view"]["state"]["values"]["code_block"]["code_input"]["value"] or ""
        pad = _get_pad(uid)
        pad[filename] = new_code
        save_state()
        await client.chat_postMessage(channel=uid, text=f":pencil2: Updated *{filename}*.")

    @app.command("/code_view")
    async def code_view(ack, command, respond):
        await ack()
        uid = command["user_id"]
        filename = (command.get("text") or "").strip()
        if not filename:
            return await respond(text="Usage: `/code_view <filename>`", response_type="ephemeral")
        pad = _get_pad(uid)
        if filename not in pad:
            return await respond(text=":x: File not found.", response_type="ephemeral")
        code = pad[filename] or "(empty)"
        if len(code) > 2900:
            code = code[:2900] + "\n...(truncated)"
        await respond(text=f"*{filename}*\n```\n{code}\n```")

    @app.command("/code_list")
    async def code_list(ack, command, respond):
        await ack()
        uid = command["user_id"]
        pad = _get_pad(uid)
        if not pad:
            return await respond(text=":open_file_folder: No files.", response_type="ephemeral")
        await respond(text=":open_file_folder: *Files:*\n" + "\n".join(f"• {fn}" for fn in pad))

    @app.command("/code_delete")
    async def code_delete(ack, command, respond):
        await ack()
        uid = command["user_id"]
        filename = (command.get("text") or "").strip()
        if not filename:
            return await respond(text="Usage: `/code_delete <filename>`", response_type="ephemeral")
        pad = _get_pad(uid)
        if filename not in pad:
            return await respond(text=":x: File not found.", response_type="ephemeral")
        del pad[filename]
        save_state()
        await respond(text=f":wastebasket: Deleted *{filename}*.")

    @app.command("/code_run")
    async def code_run(ack, command, respond):
        await ack()
        uid = command["user_id"]
        filename = (command.get("text") or "").strip()
        if not filename:
            return await respond(text="Usage: `/code_run <filename>`", response_type="ephemeral")
        pad = _get_pad(uid)
        if filename not in pad:
            return await respond(text=":x: File not found.", response_type="ephemeral")
        code = pad[filename]
        if not code.strip():
            return await respond(text=":x: File is empty.", response_type="ephemeral")
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if ext in ("cpp", "cc", "cxx"):
            output = await run_cpp(code)
        else:
            output = sandbox_exec(code)
        if len(output) > 2900:
            output = output[:2900] + "\n...<truncated>"
        await respond(text=f":computer: *Output of {filename}:*\n```\n{output}\n```")
