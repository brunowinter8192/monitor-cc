# INFRASTRUCTURE
import json
import glob
import re
import os

DIRS=sorted(glob.glob(os.path.expanduser("~/.claude/projects/-Users-brunowinter2000-Documents-ai-monitor-cc/*.jsonl")))

# ORCHESTRATOR
def extract_turns_workflow():
    turns = collect_turns(DIRS)
    out, n = build_turn_lines(turns)
    write_turns(out, n)


# FUNCTIONS
def collect_turns(dirs):
    turns=[]
    for f in dirs:
        cur=[];lastp=""
        for line in open(f,encoding="utf-8",errors="replace"):
            try:o=json.loads(line)
            except:continue
            t=o.get("type");m=o.get("message") or {}
            if t=="user":
                c=m.get("content")
                if isinstance(c,str) or (isinstance(c,list) and not any(isinstance(b,dict) and b.get("type")=="tool_result" for b in c)):
                    if cur:turns.append((f,lastp,cur))
                    cur=[];lastp=c if isinstance(c,str) else " ".join(b.get("text","") for b in c if isinstance(b,dict))
            elif t=="assistant" and "opus" in (m.get("model") or ""):
                for b in (m.get("content") or []):
                    if isinstance(b,dict) and b.get("type")=="text": cur.append(b.get("text") or "")
        if cur:turns.append((f,lastp,cur))
    return turns


def build_turn_lines(turns):
    out=[];n=0
    for f,p,blocks in turns:
        ex=split_ex("\n".join(blocks))
        if len(ex)<4: continue
        n+=1
        out.append(f"## TURN {n}  (session {os.path.basename(f)[:8]}, {len(ex)} exchanges)\n")
        out.append(f"USER: {' '.join(p.split())[:200]}\n")
        for k,(pt,bl) in enumerate(ex):
            out.append(f"[{k}] {pt}")
            for b in bl[:6]: out.append(f"    {b}")
        out.append("")
    return out, n


def split_ex(txt):
    ex=[];cur=None
    for l in txt.split("\n"):
        s=l.strip()
        if (s.startswith("**") and s.endswith("**") and len(s)>6) or s.startswith("🛑"):
            if cur:ex.append(cur)
            cur=[re.sub(r"^\*\*|\*\*$","",s),[]]
        elif cur is not None and s and not s.startswith(">"): cur[1].append(s)
    if cur:ex.append(cur)
    return ex


def write_turns(out, n):
    txt="\n".join(out)
    open("/tmp/k2_turns.md","w",encoding="utf-8").write(txt)
    print(f"turns written: {n} | chars: {len(txt)} | approx tokens: {len(txt)//3.5:.0f}")


if __name__ == '__main__':
    extract_turns_workflow()
