from economy_shared import state, save_state
import clang.cindex
from clang.cindex import Index, CursorKind, Config
import ast
import random
import datetime
import asyncio
import os
import re
import glob
import subprocess

def detect_gcc_version():
    try:
        out = subprocess.check_output(["g++", "-dumpfullversion", "-dumpversion"], text=True).strip()
        return out.split(".")[0]
    except Exception:
        return "13"

try:
    clang_path = clang.cindex.Config.library_path
    if clang_path and os.path.isdir(clang_path):
        libs = glob.glob(os.path.join(clang_path, "libclang.so*"))
        if libs:
            Config.set_library_file(libs[0])
except Exception:
    pass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None


class HackerUniverse:
    def __init__(self):
        self.openrouter_client = None
        self.groq_client = None
        self.gemini_models = []
        self.clang_index = None
        self._init_ai_clients()
        self._init_clang()

    def _init_ai_clients(self):
        or_key = os.getenv("OPENROUTER_KEY")
        if OpenAI and or_key:
            try:
                self.openrouter_client = OpenAI(
                    api_key=or_key, base_url="https://openrouter.ai/api/v1",
                    default_headers={"HTTP-Referer": "https://example.com", "X-Title": "Slack Hack RPG"},
                )
            except Exception:
                self.openrouter_client = None
        groq_key = os.getenv("GROQ")
        if Groq and groq_key:
            try: self.groq_client = Groq(api_key=groq_key)
            except Exception: self.groq_client = None
        gemini_key = os.getenv("GEMINI_API_KEY")
        if genai and gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                self.gemini_models = ["gemini-2.5-flash", "gemini-2.0-flash"]
            except Exception:
                self.gemini_models = []

    def _init_clang(self):
        try:
            self.clang_index = Index.create()
        except Exception:
            self.clang_index = None

    def get_profile(self, user_id):
        uid = str(user_id)
        state.setdefault("hacker_profiles", {})
        if uid not in state["hacker_profiles"]:
            state["hacker_profiles"][uid] = {
                "skill": 1, "xp": 0, "tier": 1, "trace": 0, "reputation": 0, "streak": 0,
                "last_hack": None, "specializations": [], "hack_history": [],
                "style_vector": {"aggressive": 0.0, "stealthy": 0.0, "bruteforce": 0.0, "elegant": 0.0, "experimental": 0.0},
                "chaos_affinity": 0.0, "chaos_unlocks": [],
            }
            save_state()
        return state["hacker_profiles"][uid]

    def get_user_pad(self, user_id):
        uid = str(user_id)
        state.setdefault("codepad", {})
        if uid not in state["codepad"]:
            state["codepad"][uid] = {}; save_state()
        pad = state["codepad"][uid]
        normalized = {}; changed = False
        for fn, val in pad.items():
            if isinstance(val, str): normalized[fn] = val
            elif isinstance(val, dict) and isinstance(val.get("content"), str): normalized[fn] = val["content"]; changed = True
            else: changed = True
        if changed: state["codepad"][uid] = normalized; save_state()
        return normalized

    def analyze_script_ast(self, filename, code):
        try: tree = ast.parse(code)
        except Exception: return None
        fn_defs = []; class_defs = loops = branches = comprehensions = calls = 0; recursion = False; max_depth = 0
        def visit(node, depth):
            nonlocal loops, branches, comprehensions, calls, recursion, max_depth, class_defs
            if depth > max_depth: max_depth = depth
            if isinstance(node, ast.FunctionDef): fn_defs.append(node.name)
            if isinstance(node, ast.ClassDef): class_defs += 1
            if isinstance(node, (ast.For, ast.While, ast.AsyncFor)): loops += 1
            if isinstance(node, (ast.If, ast.Match)): branches += 1
            if isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)): comprehensions += 1
            if isinstance(node, ast.Call):
                calls += 1
                if isinstance(node.func, ast.Name) and node.func.id in fn_defs: recursion = True
            for child in ast.iter_child_nodes(node): visit(child, depth + 1)
        visit(tree, 0)
        lines = code.splitlines(); tokens = re.findall(r"\S+", code)
        line_count = len(lines); non_empty = len([l for l in lines if l.strip()])
        token_count = len(tokens); unique_tokens = len(set(tokens))
        density = token_count / line_count if line_count else 0.0
        branching_factor = branches + loops + comprehensions
        structural_complexity = branching_factor + max_depth + (3 if recursion else 0)
        size_penalty = max(0.0, (len(code) - 2000) / 3000.0) if len(code) > 2000 else 0.0
        efficiency = max(0.1, min(10.0, 4.2 + density * 0.35 - structural_complexity * 0.05 - size_penalty * 0.7))
        elegance = max(0.1, min(10.0, 3.0 + comprehensions * 0.7 + class_defs * 0.6 - loops * 0.25))
        aggression = max(0.1, min(10.0, 1.8 + loops * 0.6 + calls * 0.2))
        stealth = max(0.1, min(10.0, 5.5 + max_depth * 0.25 - branching_factor * 0.08))
        experimental = max(0.1, min(10.0, 2.2 + (unique_tokens / max(1, token_count)) * 18.0))
        return {"filename": filename, "line_count": line_count, "non_empty": non_empty, "token_count": token_count,
                "unique_tokens": unique_tokens, "fn_defs": len(fn_defs), "class_defs": class_defs, "loops": loops,
                "branches": branches, "comprehensions": comprehensions, "calls": calls, "recursion": recursion,
                "max_depth": max_depth, "efficiency": efficiency, "elegance": elegance, "aggression": aggression,
                "stealth": stealth, "experimental": experimental}

    def analyze_cpp_libclang(self, filename, code, language):
        if not self.clang_index:
            try: self.clang_index = Index.create()
            except Exception: return None
        import tempfile
        lower = filename.lower()
        suffix = ".cpp" if language.lower() == "cpp" else (".hpp" if lower.endswith(".h") else ".c")
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=suffix) as tmp:
            tmp.write(code); tmp_path = tmp.name
        gcc_ver = detect_gcc_version()
        args = [f"-std=c++17", "-I/usr/include", f"-I/usr/include/c++/{gcc_ver}",
                f"-I/usr/include/x86_64-linux-gnu/c++/{gcc_ver}"] if language.lower() == "cpp" else ["-std=c11", "-I/usr/include"]
        try: tu = self.clang_index.parse(tmp_path, args=args)
        except Exception: tu = None
        if not tu or not getattr(tu, "cursor", None):
            lines = code.splitlines()
            return {"filename": filename, "line_count": len(lines), "non_empty": len([l for l in lines if l.strip()]),
                    "token_count": len(re.findall(r"\S+", code)), "unique_tokens": len(set(re.findall(r"\S+", code))),
                    "fn_defs": 0, "class_defs": 0, "loops": 0, "branches": 0, "comprehensions": 0, "calls": 0,
                    "recursion": False, "max_depth": 1, "efficiency": 3, "elegance": 2, "aggression": 1, "stealth": 1, "experimental": 1}
        loops = branches = fn_defs = class_defs = calls = max_depth = template_nodes = 0
        def visit(node, depth=0):
            nonlocal loops, branches, fn_defs, class_defs, calls, max_depth, template_nodes
            max_depth = max(max_depth, depth); k = node.kind
            if k in (CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD, CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR): fn_defs += 1
            if k in (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE): class_defs += 1
            if k in (CursorKind.FOR_STMT, CursorKind.WHILE_STMT, CursorKind.DO_STMT, CursorKind.CXX_FOR_RANGE_STMT): loops += 1
            if k in (CursorKind.IF_STMT, CursorKind.SWITCH_STMT, CursorKind.CASE_STMT, CursorKind.CONDITIONAL_OPERATOR): branches += 1
            if k == CursorKind.CALL_EXPR: calls += 1
            if k in (CursorKind.CLASS_TEMPLATE, CursorKind.FUNCTION_TEMPLATE, CursorKind.TYPE_REF, CursorKind.TEMPLATE_REF): template_nodes += 1
            for child in node.get_children(): visit(child, depth + 1)
        visit(tu.cursor, 0)
        lines = code.splitlines(); tokens = re.findall(r"\S+", code)
        line_count = len(lines); token_count = len(tokens); unique_tokens = len(set(tokens))
        pointer_ops = code.count("*"); ref_ops = code.count("&")
        density = token_count / line_count if line_count else 0.0
        branching_factor = branches + loops
        template_intensity = template_nodes / max(1, fn_defs + class_defs + 1)
        pointer_intensity = (pointer_ops + ref_ops) / max(1, line_count)
        efficiency = max(0.1, min(10.0, 4.0 + density * 0.25 - (branching_factor + max_depth) * 0.03))
        elegance = max(0.1, min(10.0, 2.8 + class_defs * 0.6 + template_intensity * 4.0 - loops * 0.2))
        aggression = max(0.1, min(10.0, 2.5 + loops * 0.6 + calls * 0.2 + pointer_intensity * 3.0))
        stealth = max(0.1, min(10.0, 4.5 - max_depth * 0.05 - branching_factor * 0.05 + template_intensity * 2.0))
        experimental = max(0.1, min(10.0, 1.5 + unique_tokens / max(1, token_count) * 10.0 + template_intensity * 5.0))
        return {"filename": filename, "line_count": line_count, "non_empty": len([l for l in lines if l.strip()]),
                "token_count": token_count, "unique_tokens": unique_tokens, "fn_defs": fn_defs, "class_defs": class_defs,
                "loops": loops, "branches": branches, "comprehensions": 0, "calls": calls, "recursion": False,
                "max_depth": max_depth, "efficiency": efficiency, "elegance": elegance, "aggression": aggression,
                "stealth": stealth, "experimental": experimental}

    def infer_archetype(self, filename, stats, code):
        name = filename.lower()
        if any(k in name for k in ["recon","scan","probe","map","survey","spider"]): return "recon"
        if any(k in name for k in ["auth","login","access","breakin","door","key"]): return "access"
        if any(k in name for k in ["payload","inject","exploit","shell","bomb","virus"]): return "payload"
        if any(k in name for k in ["exfil","extract","leak","proxy","tunnel","drain","smuggle"]): return "extraction"
        if any(k in name for k in ["core","util","common","shared","base","engine"]): return "support"
        text = code.lower()
        if "socket" in text or "request" in text or "http" in text: return "recon"
        if "encrypt" in text or "decrypt" in text or "hash" in text: return "access"
        if "compress" in text or "payload" in text or "packet" in text: return "payload"
        if "proxy" in text or "route" in text or "exfil" in text: return "extraction"
        return "generic"

    def script_language(self, filename, code):
        lower = filename.lower()
        if lower.endswith(".py"): return "python"
        if any(lower.endswith(e) for e in (".cpp",".cxx",".cc",".hpp")): return "cpp"
        if any(lower.endswith(e) for e in (".c",".h")):
            return "cpp" if any(k in code for k in ("class ","template<","std::")) else "c"
        return "python"

    def rarity_from_stats(self, stats):
        score = stats["efficiency"] + stats["elegance"] + stats["stealth"] + stats["experimental"] + stats["aggression"]
        if score >= 40: return "mythic"
        if score >= 32: return "legendary"
        if score >= 25: return "epic"
        if score >= 18: return "rare"
        return "common"

    def chaos_weight(self, stats, lang):
        base = stats["experimental"] + stats["aggression"]
        base *= {"cpp": 1.35, "c": 1.2, "python": 1.05}.get(lang, 1.0)
        return base * (0.8 + (stats["max_depth"] + stats["loops"]) * 0.03)

    def analyze_all_scripts(self, pad):
        analyses = {}
        for fn, code in pad.items():
            if not isinstance(code, str) or not code.strip(): continue
            lang = self.script_language(fn, code).lower()
            ast_stats = self.analyze_cpp_libclang(fn, code, lang) if lang in ("c","cpp") else self.analyze_script_ast(fn, code)
            if ast_stats is None: continue
            analyses[fn] = {
                "filename": fn, "language": lang,
                "archetype": self.infer_archetype(fn, ast_stats, code),
                "rarity": self.rarity_from_stats(ast_stats),
                "ast": ast_stats, "chaos": self.chaos_weight(ast_stats, lang),
            }
        return analyses

    def select_modules(self, analyses, recon_name, access_name, payload_name, extract_name):
        def pick(name, role):
            if name and name in analyses: return analyses[name]
            candidates = sorted([a for a in analyses.values() if a["archetype"] == role] or list(analyses.values()),
                                 key=lambda a: sum(a["ast"][k] for k in ("efficiency","elegance","stealth","experimental")), reverse=True)
            return candidates[0] if candidates else None
        modules = {"recon": pick(recon_name,"recon"), "access": pick(access_name,"access"),
                   "payload": pick(payload_name,"payload"), "extraction": pick(extract_name,"extraction")}
        usage = {}
        for mod in modules.values():
            if mod: usage[mod["filename"]] = usage.get(mod["filename"], 0) + 1
        for mod in modules.values():
            if mod: mod["reuse_count"] = usage.get(mod["filename"], 1)
        return modules

    def get_target_space(self):
        state.setdefault("hack_targets", {}); save_state()
        return state["hack_targets"]

    def get_or_create_target(self, target_id, difficulty):
        space = self.get_target_space(); key = f"{target_id}:{difficulty}"
        if key in space: return space[key]
        profile = {
            "id": key, "name": target_id, "difficulty": difficulty,
            "security_integrity": 40 + difficulty * 25, "anomaly_detection": 15 + difficulty * 15,
            "bandwidth_pressure": 20 + difficulty * 10, "forensic_risk": 15 + difficulty * 18,
            "temperament": random.choice(["paranoid","adaptive","lazy","spiky","bursty","evasive","erratic"]),
            "style_bias": {k: random.uniform(-0.3, 0.4) for k in ("aggressive","stealthy","bruteforce","elegant","experimental")},
            "battles": 0, "wins": 0, "losses": 0,
        }
        space[key] = profile; save_state(); return profile

    async def generate_target_lore(self, target_profile, chaos_level):
        name = target_profile["name"]; difficulty = target_profile["difficulty"]; temperament = target_profile["temperament"]
        chaos_tag = {3: " The topology jitters between states.", 2: " Its logs hum with anomalies.", 1: ""}.get(chaos_level, "")
        fallback = f"The {name} node is a difficulty {difficulty} defense with {temperament} behavior." + chaos_tag
        if not self.openrouter_client and not self.groq_client and not self.gemini_models:
            return fallback
        messages = [
            {"role": "system", "content": "Generate a short 1-3 sentence flavor blurb about a fictional network target. No markdown."},
            {"role": "user", "content": f"Describe target '{name}', temperament '{temperament}', chaos {chaos_level}."},
        ]
        for client, model in [(self.openrouter_client, "meta-llama/llama-3.1-70b-instruct"),
                              (self.groq_client, "llama-3.1-8b-instant")]:
            if not client: continue
            try:
                resp = await asyncio.get_event_loop().run_in_executor(
                    None, lambda c=client, m=model: c.chat.completions.create(model=m, messages=messages, max_tokens=80, temperature=0.9))
                txt = resp.choices[0].message.content.strip()
                if txt: return txt
            except Exception: pass
        if self.gemini_models:
            try:
                model = genai.GenerativeModel(self.gemini_models[0])
                resp = await asyncio.get_event_loop().run_in_executor(None, lambda: model.generate_content(messages[-1]["content"]))
                if hasattr(resp, "text") and resp.text: return resp.text.strip()
            except Exception: pass
        return fallback

    def update_style_vector(self, profile, analyses, chaos_level):
        v = profile.get("style_vector") or {k: 0.0 for k in ("aggressive","stealthy","bruteforce","elegant","experimental")}
        total = {k: 0.0 for k in v}; count = 0; cpp_chaos = 0.0
        for mod in analyses.values():
            a = mod["ast"]
            total["aggressive"] += a["aggression"]; total["stealthy"] += a["stealth"]
            total["bruteforce"] += min(10, a["loops"] + a["branches"]); total["elegant"] += a["elegance"]
            total["experimental"] += a["experimental"]
            if mod.get("language") in ("c","cpp"): cpp_chaos += mod.get("chaos", 0.0)
            count += 1
        if count == 0: profile["style_vector"] = v; return profile
        for k in total: v[k] = v.get(k, 0.0) * 0.7 + (total[k] / count) * 0.3
        affinity = max(0.0, min(100.0, profile.get("chaos_affinity", 0.0) + cpp_chaos * 0.01 + chaos_level * 0.5))
        profile["style_vector"] = v; profile["chaos_affinity"] = affinity
        unlocks = set(profile.get("chaos_unlocks", []))
        if affinity >= 60: unlocks.add("storm")
        if affinity >= 80: unlocks.add("singularity")
        profile["chaos_unlocks"] = list(unlocks)
        return profile

    def difficulty_profile(self, target_profile, style_vector, chaos_level):
        s = target_profile; bias = s["style_bias"]; scale = 0.05
        ag = style_vector.get("aggressive", 0.0); st = style_vector.get("stealthy", 0.0)
        br = style_vector.get("bruteforce", 0.0); el = style_vector.get("elegant", 0.0); ex = style_vector.get("experimental", 0.0)
        sec = s["security_integrity"] * (1 + (bias["aggressive"] * scale * ag - bias["elegant"] * scale * el))
        anom = s["anomaly_detection"] * (1 + (bias["experimental"] * scale * ex - bias["stealthy"] * scale * st))
        bw = s["bandwidth_pressure"] * (1 + bias["bruteforce"] * scale * br)
        forensic = s["forensic_risk"] * (1 + (bias["stealthy"] * scale * st - bias["aggressive"] * scale * ag))
        if chaos_level >= 3 and s["temperament"] in ("erratic","bursty"):
            anom *= random.uniform(0.8, 1.25); sec *= random.uniform(0.9, 1.15)
        elif chaos_level == 2:
            anom *= random.uniform(0.95, 1.15)
        return {"security_integrity": sec, "anomaly_detection": anom, "bandwidth_pressure": bw, "forensic_risk": forensic}

    def compute_profile_modifiers(self, profile, difficulty, chaos_level):
        skill = profile.get("skill", 1); tier = profile.get("tier", 1); trace = profile.get("trace", 0)
        rep = profile.get("reputation", 0); streak = profile.get("streak", 0)
        base = 1.0 + min(1.5, (skill - 1) * 0.03 + (tier - 1) * 0.08 + rep * 0.02)
        streak_bonus = 1.0 + min(0.5, streak * 0.05)
        trace_penalty = 1.0 + min(0.9, trace * 0.05)
        chaos_scalar = 1.0 + profile.get("chaos_affinity", 0.0) * 0.01 * chaos_level * 0.08
        global_mod = base * streak_bonus * chaos_scalar
        return {
            "global": global_mod, "trace_penalty": trace_penalty,
            "recon": 1.0 + min(0.35, (skill+tier)*0.012 + chaos_level*0.015),
            "access": 1.0 + min(0.40, (skill+tier)*0.014 + chaos_level*0.015),
            "payload": 1.0 + min(0.40, (skill+tier)*0.014 + chaos_level*0.020),
            "extraction": 1.0 + min(0.35, (skill+tier)*0.012 + chaos_level*0.010),
            "chaos_level": chaos_level, "difficulty": difficulty,
        }

    def compute_phase_score(self, phase, module, profile_mod, diff_profile, profile, target_profile):
        chaos_level = profile_mod.get("chaos_level", 0)
        if not module:
            base_power = 8.0; script_factor = 2.0
        else:
            a = module["ast"]; lang = module.get("language","python")
            if phase == "recon": base_power = a["efficiency"]*1.2 + a["stealth"]*1.4 + a["experimental"]*0.8; script_factor = a["elegance"] + a["loops"]*0.4
            elif phase == "access": base_power = a["efficiency"]*1.5 + a["aggression"]*1.1 + a["branches"]*0.7; script_factor = a["calls"]*0.4 + a["max_depth"]*0.5
            elif phase == "payload": base_power = a["elegance"]*1.4 + a["experimental"]*1.1 + a["efficiency"]; script_factor = a["comprehensions"]*0.8 + a["class_defs"]*0.6
            else: base_power = a["stealth"]*1.6 + a["efficiency"] + a["experimental"]*0.6; script_factor = a["max_depth"]*0.4 + a["fn_defs"]*0.3
            if a["fn_defs"] <= 1 and a["loops"] <= 1 and a["line_count"] < 30: base_power *= 0.6
            base_power *= {"python": 1.05, "c": 1.12 if phase in ("access","payload") else 1.0, "cpp": 1.18 if phase != "recon" else 1.0}.get(lang, 1.0)
            script_factor *= {"cpp": 1.25}.get(lang, 1.0)
            if chaos_level >= 2: base_power *= 1.0 + module.get("chaos",0.0)*0.0009; script_factor *= 1.0 + module.get("chaos",0.0)*0.0006
        temperament = target_profile["temperament"]
        base_power *= {"paranoid": 0.9 if phase in ("recon","access") else 1.0, "lazy": 1.1 if phase=="recon" else 1.0,
                       "bursty": 1.05 if phase=="payload" else 1.0, "evasive": 0.9 if phase=="extraction" else 1.0}.get(temperament, 1.0)
        if temperament == "erratic" and chaos_level >= 2: base_power *= random.uniform(0.75, 1.25)
        if phase == "recon": th = diff_profile["security_integrity"]*0.75 + diff_profile["anomaly_detection"]*0.5; bonus = profile_mod["recon"]
        elif phase == "access": th = diff_profile["security_integrity"]*1.25 + diff_profile["anomaly_detection"]*0.7; base_power = min(base_power, th*1.4); bonus = profile_mod["access"]
        elif phase == "payload": th = diff_profile["bandwidth_pressure"]*1.0 + diff_profile["security_integrity"]*0.8; bonus = profile_mod["payload"]
        else: th = diff_profile["forensic_risk"]*1.0 + diff_profile["anomaly_detection"]*0.8; bonus = profile_mod["extraction"]
        th *= profile_mod["trace_penalty"] * (1.0 + 0.30 * (profile_mod.get("difficulty",1) - 1))
        reuse = module.get("reuse_count",1) if module else 1
        power = min((base_power * profile_mod["global"] * bonus * (1.0 + chaos_level*0.08) * (0.55**(reuse-1))) + script_factor*1.1, th*3.0)
        margin = power - th; success = margin >= 0.0
        closeness = abs(margin) / max(1.0, th)
        rng_window = max(0.0, {3: 0.4, 2: 0.3, 1: 0.23, 0: 0.18}.get(chaos_level, 0.18) - closeness)
        chaos_event = None; flipped = False
        if rng_window > 0:
            roll = random.random()
            if roll < rng_window * (0.18 + 0.08*chaos_level): power *= random.uniform(0.55, 0.85); chaos_event = "entropy_collapse"; margin = power - th; success = margin >= 0.0; flipped = True
            elif margin < 0 and roll < rng_window*0.55: success = True; flipped = True; chaos_event = "lucky_break"
            elif margin > 0 and roll < rng_window*0.3: success = False; flipped = True; chaos_event = "traceback_spike"
        quality = ("flawless" if margin > th*0.3 else "barely" if margin < th*0.05 else "clean") if success else ("almost" if margin > -th*0.1 else "failed")
        return {"phase": phase, "module": module, "power": power, "threshold": th, "margin": margin, "success": success, "flipped": flipped, "quality": quality, "chaos_event": chaos_event}

    def aggregate_outcome(self, phase_results, chaos_level, difficulty):
        successes = [p for p in phase_results if p["success"]]
        flawless = sum(1 for p in phase_results if p["quality"] == "flawless")
        barely = sum(1 for p in phase_results if p["quality"] == "barely")
        almost = sum(1 for p in phase_results if p["quality"] == "almost")
        fail_count = sum(1 for p in phase_results if not p["success"])
        if any(p["phase"] == "recon" and not p["success"] for p in phase_results): success = False
        elif difficulty >= 5: success = all(p["success"] for p in phase_results) and flawless >= 2
        elif difficulty >= 4: success = all(p["success"] for p in phase_results)
        else: success = len(successes) >= 3 or (len(successes) >= 2 and flawless >= 1)
        if difficulty >= 3 and any(p["quality"] in ("barely","almost") for p in phase_results): success = False
        if success:
            if flawless >= 2 and fail_count == 0: quality = "perfect_chain"
            elif flawless >= 1 and barely == 0 and fail_count == 0: quality = "strong"
            elif barely >= 1: quality = "shaky"
            else: quality = "clean"
        else:
            quality = "near_miss" if almost >= 2 else "catastrophic" if fail_count == 4 else "messy"
        archetypes = [p["module"]["archetype"] for p in phase_results if p["module"]]
        languages = [p["module"]["language"] for p in phase_results if p["module"] and "language" in p["module"]]
        chaos_events = [p["chaos_event"] for p in phase_results if p.get("chaos_event")]
        synergy = 0.0
        if archetypes:
            if len(set(archetypes)) == 1: synergy += 0.15
            if len(set(archetypes)) >= 3: synergy += 0.15
        if languages:
            if len(set(languages)) >= 3: synergy += 0.1
            if len(set(languages)) == 1: synergy += 0.05
        if chaos_level >= 2 and chaos_events: synergy += min(0.25, len(chaos_events)*0.05)
        if chaos_level >= 3 and quality == "perfect_chain" and fail_count == 0: quality = "singularity"
        return {"success": success, "quality": quality, "synergy": synergy, "flawless": flawless, "fails": fail_count, "chaos_events": chaos_events}

    def apply_progression(self, profile, difficulty, outcome, phase_results, target_profile, chaos_level):
        base_xp = int(14 * (difficulty**1.35))
        mult = {"perfect_chain": 2.4, "strong": 1.8, "clean": 1.4, "shaky": 1.1, "near_miss": 0.8, "catastrophic": 0.35, "singularity": 3.2}.get(outcome["quality"], 0.5)
        xp_gain = int(base_xp * mult * (1.0 + chaos_level*0.2))
        sk = rep = tr = 0
        if outcome["success"]:
            sk = 1 + difficulty // 2; rep = 1 + difficulty; tr = -1
            for p in phase_results:
                if p["success"] and p["quality"] == "flawless": sk += 1; rep += 1
            profile["chaos_affinity"] = max(0, min(100, profile.get("chaos_affinity",0) + chaos_level*1.5))
        else:
            tr = 1 + difficulty
            if profile.get("skill",1) > 3: sk = -1
            rep = -1
            profile["chaos_affinity"] = max(0, min(100, profile.get("chaos_affinity",0) + chaos_level*0.5))
        if outcome["quality"] == "singularity": sk += 3; rep += 5; profile["chaos_affinity"] = min(100, profile.get("chaos_affinity",0)+10)
        profile["xp"] = profile.get("xp",0) + xp_gain
        profile["skill"] = max(1, profile.get("skill",1)+sk)
        profile["reputation"] = max(0, profile.get("reputation",0)+rep)
        profile["trace"] = max(0, min(40, profile.get("trace",0)+tr))
        profile["streak"] = profile.get("streak",0)+1 if outcome["success"] else 0
        while profile["xp"] >= 120 * profile.get("tier",1): profile["xp"] -= 120*profile["tier"]; profile["tier"] += 1
        space = self.get_target_space(); tid = target_profile["id"]
        if tid in space:
            t = space[tid]; t["battles"] += 1
            if outcome["success"]:
                t["losses"] += 1
                for k in ("security_integrity","anomaly_detection","forensic_risk","bandwidth_pressure"):
                    t[k] *= 1.06 + difficulty*0.02
            else:
                t["wins"] += 1
                for k in ("security_integrity","anomaly_detection","forensic_risk","bandwidth_pressure"):
                    t[k] *= 1.10 + difficulty*0.04
        save_state()
        return {"xp_gain": xp_gain, "skill_delta": sk, "rep_delta": rep, "trace_delta": tr}

    def compute_cooldown(self, profile, difficulty, chaos_level):
        base = 45 + difficulty*25 + profile.get("trace",0)*3 - profile.get("skill",1)*1.5 - profile.get("tier",1)*3
        base -= profile.get("chaos_affinity",0)*0.3 + chaos_level*6
        return max(10, min(900, int(base)))

    def format_module_summary(self, modules):
        parts = []
        for key in ("recon","access","payload","extraction"):
            mod = modules.get(key)
            if not mod: parts.append(f"{key.title()}: none"); continue
            a = mod["ast"]
            parts.append(f"{key.title()}: `{mod['filename']}` [{mod.get('language','?')}/{mod.get('rarity','?')}] eff={a['efficiency']:.1f} stl={a['stealth']:.1f} agg={a['aggression']:.1f} elg={a['elegance']:.1f}")
        return "\n".join(parts)

    def format_profile_status(self, profile):
        sv = profile.get("style_vector",{}); ca = profile.get("chaos_affinity",0.0); unlocks = profile.get("chaos_unlocks",[])
        return (f"Skill: *{profile.get('skill',1)}*  Tier: *{profile.get('tier',1)}*  XP: *{profile.get('xp',0)}*\n"
                f"Trace: *{profile.get('trace',0)}/40*  Rep: *{profile.get('reputation',0)}*  Streak: *{profile.get('streak',0)}*\n"
                f"Chaos: *{ca:.1f}*  Unlocks: {', '.join(unlocks) or 'none'}\n"
                + (f"Style → Aggr={sv.get('aggressive',0):.1f} Stl={sv.get('stealthy',0):.1f} Brute={sv.get('bruteforce',0):.1f} Elg={sv.get('elegant',0):.1f} Exp={sv.get('experimental',0):.1f}" if sv else ""))

    def format_target_status(self, t):
        return (f"Sec={t['security_integrity']:.1f} Anom={t['anomaly_detection']:.1f} "
                f"BW={t['bandwidth_pressure']:.1f} Forensic={t['forensic_risk']:.1f} "
                f"Temperament={t['temperament']} Record={t['wins']}W/{t['losses']}L")

    def build_final_text(self, uid, target, modules, profile, difficulty, target_profile, phase_results, outcome, progression, lore, chaos_level):
        success = outcome["success"]
        badge = {3: ("chaos singularity" if outcome["quality"]=="singularity" else "full desync"), 2: ("stochastic edge" if outcome["quality"] in ("perfect_chain","strong","singularity") else "unstable edge"), 1: "soft entropy", 0: "calm stack"}.get(chaos_level, "calm stack")
        icon = ":white_check_mark:" if success else ":x:"
        title = f"{icon} *{'Breach Complete' if success else 'Intrusion Disrupted'}: {target}* [{badge}]"
        name_map = {"recon":"Recon","access":"Access","payload":"Payload","extraction":"Extraction"}
        phase_lines = []
        for res in phase_results:
            label = name_map.get(res["phase"],res["phase"])
            sym = ":gem:" if res["quality"]=="flawless" else (":white_check_mark:" if res["success"] else ":x:")
            mod_name = res["module"]["filename"] if res["module"] else "no module"
            margin_pct = res["margin"] / max(1.0, res["threshold"])
            chaos_tag = {
                "lucky_break": " ✨lucky", "traceback_spike": " ☢trace", "entropy_collapse": " ⚡desync"
            }.get(res.get("chaos_event"), "")
            phase_lines.append(f"{sym} {label} `{mod_name}` {res['power']:.1f}/{res['threshold']:.1f} ({margin_pct*100:.0f}%) {res['quality']}{chaos_tag}")
        out = [title, "```\n" + "\n".join(phase_lines) + "\n```"]
        out.append(f"Chain: *{outcome['quality']}*  XP: *+{progression['xp_gain']}*  Skill: *{progression['skill_delta']:+d}*  Rep: *{progression['rep_delta']:+d}*  Trace: *{progression['trace_delta']:+d}*")
        if outcome["chaos_events"]: out.append(f"Anomalies: {', '.join(set(outcome['chaos_events']))}")
        out.append(f"*Modules:*\n{self.format_module_summary(modules)}")
        out.append(f"*Hacker:*\n{self.format_profile_status(profile)}")
        out.append(f"*Target:*\n{self.format_target_status(target_profile)}")
        if lore: out.append(f"_Lore: {lore}_")
        return "\n".join(out)

    async def animate_hack(self, client, channel, ts, target, modules, difficulty, target_profile, chaos_level):
        phases = [
            ("recon","Reconnaissance","📡",["Mapping endpoints","Fingerprinting defenses","Sampling telemetry","Building topology"]),
            ("access","Access Vector","🧬",["Normalizing credentials","Aligning solver","Injecting probes","Deforming auth surface"]),
            ("payload","Payload","💾",["Assembling segments","Encrypting","Scrambling signatures","Priming execution"]),
            ("extraction","Exfiltration","🚀",["Splicing streams","Braiding proxies","Masking envelopes","Evacuating channels"]),
        ]
        chaos_label = {0:"stabilized",1:"jitter",2:"storm",3:"anomaly cascade"}
        for key, label, icon, steps in phases:
            mod = modules.get(key); mod_name = mod["filename"] if mod else "no module"
            for i in range(len(steps)):
                rows = [("✅" if idx < i else "🟡" if idx == i else "⚪") + " " + step for idx, step in enumerate(steps)]
                text = f"*{icon} {label} → {target}*\n```\n" + "\n".join(rows) + "\n```"
                text += f"\nModule: `{mod_name}` | Difficulty: {difficulty} | Chaos: {chaos_label.get(chaos_level,'?')}"
                try:
                    await client.chat_update(channel=channel, ts=ts, text=text)
                except Exception:
                    pass
                await asyncio.sleep(0.6)


_engine = HackerUniverse()


async def setup(app):

    async def _run_hack(uid, channel, client, target, difficulty, chaos_level, recon_file, access_file, payload_file, extract_file):
        profile = _engine.get_profile(uid)
        now = datetime.datetime.utcnow()
        last_raw = profile.get("last_hack")
        cd = _engine.compute_cooldown(profile, difficulty, chaos_level)
        if last_raw:
            try:
                delta = (now - datetime.datetime.fromisoformat(last_raw)).total_seconds()
                if delta < cd:
                    await client.chat_postEphemeral(channel=channel, user=uid, text=f":hourglass: Rigs recalibrating. Try in *{int(cd-delta)}s*.")
                    return
            except Exception: pass
        pad = _engine.get_user_pad(uid)
        analyses = _engine.analyze_all_scripts(pad)
        if not analyses:
            await client.chat_postEphemeral(channel=channel, user=uid, text=":x: No usable scripts. Use `/code_new` and `/code_edit` first.")
            return
        profile = _engine.update_style_vector(profile, analyses, chaos_level)
        target_profile = _engine.get_or_create_target(target, difficulty)
        diff_profile = _engine.difficulty_profile(target_profile, profile.get("style_vector",{}), chaos_level)
        modules = _engine.select_modules(analyses, recon_file, access_file, payload_file, extract_file)
        profile["last_hack"] = now.isoformat(); save_state()
        lore = await _engine.generate_target_lore(target_profile, chaos_level)
        intro = (f":zap: *Initializing intrusion → {target}*\n"
                 f"Difficulty: {difficulty} | Chaos: {chaos_level}\n"
                 f"{_engine.format_profile_status(profile)}\n"
                 f"*Modules:*\n{_engine.format_module_summary(modules)}\n"
                 f"*Target:*\n{_engine.format_target_status(target_profile)}"
                 + (f"\n_{lore}_" if lore else ""))
        result = await client.chat_postMessage(channel=channel, text=intro)
        ts = result["ts"]
        await _engine.animate_hack(client, channel, ts, target, modules, difficulty, target_profile, chaos_level)
        profile_mod = _engine.compute_profile_modifiers(profile, difficulty, chaos_level)
        recon_res = _engine.compute_phase_score("recon", modules.get("recon"), profile_mod, diff_profile, profile, target_profile)
        access_res = _engine.compute_phase_score("access", modules.get("access"), profile_mod, diff_profile, profile, target_profile)
        payload_res = _engine.compute_phase_score("payload", modules.get("payload"), profile_mod, diff_profile, profile, target_profile)
        extract_res = _engine.compute_phase_score("extraction", modules.get("extraction"), profile_mod, diff_profile, profile, target_profile)
        if not recon_res["success"]:
            for r in (access_res, payload_res, extract_res):
                r["power"] *= 0.5; r["power"] -= r["threshold"]*0.15
        if not access_res["success"]:
            payload_res["power"] *= 0.75; extract_res["power"] *= 0.8
        for r in (access_res, payload_res, extract_res):
            r["power"] = min(r["power"], r["threshold"]*3.0); r["margin"] = r["power"] - r["threshold"]
            r["success"] = r["margin"] >= 0.0
            r["quality"] = ("flawless" if recon_res["success"] and r["margin"] > r["threshold"]*0.35 else "barely" if r["margin"] < r["threshold"]*0.08 else "clean") if r["success"] else ("almost" if r["margin"] > -r["threshold"]*0.12 else "failed")
        phases = [recon_res, access_res, payload_res, extract_res]
        outcome = _engine.aggregate_outcome(phases, chaos_level, difficulty)
        progression = _engine.apply_progression(profile, difficulty, outcome, phases, target_profile, chaos_level)
        profile.setdefault("hack_history", []).append({"target": target, "difficulty": difficulty, "success": outcome["success"], "quality": outcome["quality"], "chaos": chaos_level, "timestamp": now.isoformat()})
        profile["hack_history"] = profile["hack_history"][-30:]; save_state()
        final_text = _engine.build_final_text(uid, target, modules, profile, difficulty, target_profile, phases, outcome, progression, lore, chaos_level)
        await client.chat_update(channel=channel, ts=ts, text=final_text)

    @app.command("/fus_hack")
    async def hack(ack, command, client, respond):
        await ack()
        uid = command["user_id"]; channel = command["channel_id"]
        args = (command.get("text") or "").split()
        if not args:
            return await client.chat_postEphemeral(channel=channel, user=uid, text="Usage: `/fus_hack <target> [difficulty=2] [chaos=0]` | `/fus_hack profile` | `/fus_hack targets` | `/fus_hack state` | `/fus_hack chaos <target>`")
        sub = args[0].lower()

        if sub == "profile":
            import re as re_mod
            rest = " ".join(args[1:])
            m = re_mod.search(r"<@([A-Z0-9]+)>", rest)
            target_uid = m.group(1) if m else uid
            profile = _engine.get_profile(target_uid)
            hist = profile.get("hack_history", [])
            lines = [f"{'✅' if h.get('success') else '❌'} {h.get('target','?')} d={h.get('difficulty',0)} c={h.get('chaos',0)} q={h.get('quality','?')}" for h in hist[-10:]]
            history_text = "\n".join(lines) or "No runs yet."
            await respond(text=f"*Hacker Profile*\n{_engine.format_profile_status(profile)}\n\n*Recent Runs:*\n{history_text}")

        elif sub == "targets":
            space = _engine.get_target_space()
            if not space:
                return await respond(text="No targets yet. Run `/fus_hack <target>` first.", response_type="ephemeral")
            lines = [f"• {t['name']} d={t['difficulty']} {t['wins']}W/{t['losses']}L sec={t['security_integrity']:.0f}" for t in list(space.values())[:30]]
            await respond(text="*Known Targets:*\n" + "\n".join(lines))

        elif sub == "state":
            profile = _engine.get_profile(uid)
            ca = profile.get("chaos_affinity", 0.0); unlocks = profile.get("chaos_unlocks", [])
            sv = profile.get("style_vector", {})
            await respond(text=f"*Chaos State*\nResonance: *{ca:.1f}*\nUnlocks: {', '.join(unlocks) or 'none'}\nAggressive: {sv.get('aggressive',0):.1f}  Experimental: {sv.get('experimental',0):.1f}")

        elif sub == "chaos":
            if len(args) < 2:
                return await client.chat_postEphemeral(channel=channel, user=uid, text="Usage: `/fus_hack chaos <target> [difficulty=3]`")
            target = args[1]; difficulty = 3
            for a in args[2:]:
                if a.startswith("difficulty="): difficulty = int(a.split("=", 1)[1])
            asyncio.ensure_future(_run_hack(uid, channel, client, target, max(1, min(5, difficulty)), 3, None, None, None, None))

        else:
            target = args[0]
            opts = {"difficulty": 2, "chaos": 0, "recon": None, "access": None, "payload": None, "extract": None}
            for a in args[1:]:
                if "=" in a:
                    k, v = a.split("=", 1)
                    if k in ("difficulty", "chaos"): opts[k] = int(v)
                    else: opts[k] = v
            difficulty = max(1, min(5, opts["difficulty"]))
            chaos_level = max(0, min(3, opts["chaos"]))
            asyncio.ensure_future(_run_hack(uid, channel, client, target, difficulty, chaos_level, opts["recon"], opts["access"], opts["payload"], opts["extract"]))
