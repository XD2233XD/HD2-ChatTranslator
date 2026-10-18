"""游戏黑话 / 缩写词典。

两层用法：
  1. 整条消息精确命中（忽略大小写与首尾标点）→ 直接给出译文，零延迟、不依赖模型；
  2. 没命中 → 作为提示词的一部分交给模型，要求按游戏语境推断，禁止逐字母直译。

只收“按字面翻一定错”的词；普通单词交给模型。
"""
from __future__ import annotations

import re

# 英文/国际服黑话 -> 中文
EN = {
    "sr": ("抱歉", "sorry (apology)"),
    "sry": ("抱歉", "sorry"),
    "sorry": ("抱歉", "sorry"),
    "lol": ("哈哈", "laughing out loud"),
    "lmao": ("笑死", "laughing my ass off"),
    "lmfao": ("笑死", "laughing my fucking ass off"),
    "rofl": ("笑翻", "rolling on the floor laughing"),
    "gg": ("打得好", "good game"),
    "ggwp": ("打得好，辛苦了", "good game, well played"),
    "wp": ("打得漂亮", "well played"),
    "gj": ("干得好", "good job"),
    "n1": ("漂亮", "nice one"),
    "ty": ("谢谢", "thank you"),
    "thx": ("谢谢", "thanks"),
    "tnx": ("谢谢", "thanks"),
    "np": ("不客气", "no problem"),
    "mb": ("我的错", "my bad"),
    "myb": ("我的错", "my bad"),
    "afk": ("暂离一下", "away from keyboard"),
    "brb": ("马上回来", "be right back"),
    "gtg": ("得走了", "got to go"),
    "cya": ("回头见", "see you"),
    "cu": ("回头见", "see you"),
    "omg": ("我的天", "oh my god"),
    "wtf": ("什么鬼", "what the fuck"),
    "ez": ("太简单了", "easy (often mocking)"),
    "noob": ("菜鸟", "newbie"),
    "nub": ("菜鸟", "newbie"),
    "op": ("太强了", "overpowered"),
    "buff": ("加强", "buff"),
    "nerf": ("削弱", "nerf"),
    "dps": ("输出", "damage per second"),
    "aggro": ("仇恨", "enemy aggro"),
    "aoe": ("范围伤害", "area of effect"),
    "cd": ("冷却", "cooldown"),
    "hp": ("血量", "health"),
    "mp": ("蓝量", "mana"),
    "pvp": ("玩家对战", "player versus player"),
    "pve": ("打怪", "player versus environment"),
    "gl": ("好运", "good luck"),
    "hf": ("玩得开心", "have fun"),
    "ngl": ("说实话", "not gonna lie"),
    "tbh": ("说实话", "to be honest"),
    "imo": ("我觉得", "in my opinion"),
    "imho": ("我个人觉得", "in my humble opinion"),
    "idk": ("不知道", "I don't know"),
    "idc": ("无所谓", "I don't care"),
    "rn": ("现在", "right now"),
    "pls": ("请", "please"),
    "plz": ("请", "please"),
    "u": ("你", "you"),
    "ur": ("你的", "your / you're"),
    "r": ("是", "are"),
    "k": ("好", "ok"),
    "y": ("是", "yes"),
    "n": ("不", "no"),
    "o7": ("敬礼", "salute"),
    "07": ("敬礼", "salute"),
    "wb": ("欢迎回来", "welcome back"),
    "sup": ("怎么样", "what's up"),
    "yo": ("嘿", "hey"),
    "fr": ("真的", "for real"),
    "ong": ("真的", "on god"),
    "bet": ("行", "okay / bet"),
    "cap": ("吹牛", "lie / cap"),
    "nocap": ("没吹牛", "no lie"),
    "ez clap": ("轻松拿下", "easy win"),
    "ggs": ("打得好", "good games"),
    "rip": ("完了", "rest in peace / we're dead"),
    "f": ("默哀", "press F to pay respects"),
    "pog": ("厉害了", "pogchamp / impressive"),
    "poggers": ("厉害了", "impressive"),
    "sus": ("可疑", "suspicious"),
    "chill": ("别急", "calm down"),
    "toxic": ("嘴臭", "toxic"),
    "throw": ("送输", "throw the game"),
    "throwing": ("在送", "throwing the game"),
    "int": ("故意送", "intentionally feeding"),
    "smurf": ("开小号", "smurf account"),
    "clutch": ("关键救场", "clutch play"),
    "carry": ("带飞", "carry"),
    "feed": ("送人头", "feeding"),
    # Helldivers 2 专用缩写：直译没用，给出中文名并保留缩写便于对照
    "rr": ("无后座力炮（RR）", "recoilless rifle"),
    "eat": ("一次性反坦克（EAT）", "expendable anti-tank"),
    "amr": ("反器材步枪（AMR）", "anti-materiel rifle"),
    "hmg": ("重机枪（HMG）", "heavy machine gun"),
    "sc": ("超级货币（SC）", "super credits"),
    "frv": ("快速侦察载具（FRV）", "fast recon vehicle"),
    "exo": ("机甲（EXO）", "exosuit"),
    "sos": ("求救信标（SOS）", "SOS beacon"),
    "500kg": ("500kg 炸弹", "500kg bomb"),
    "hellbomb": ("地狱火炸弹", "hellbomb"),
    "strat": ("战备", "stratagem"),
    "evac": ("撤离", "evacuation"),
    "extract": ("撤离", "extraction"),
    "bug": ("虫族", "Terminid"),
    "bugs": ("虫族", "Terminids"),
    "bot": ("机器人", "Automaton"),
    "bots": ("机器人", "Automatons"),
}

# 中文黑话 -> 英文
ZH = {
    "6": ("nice", "6 (praise)"),
    "666": ("awesome", "666 (praise)"),
    "牛": ("awesome", "niu / awesome"),
    "牛逼": ("awesome", "awesome"),
    "牛批": ("awesome", "awesome"),
    "草": ("damn", "cao / damn"),
    "卧槽": ("wtf", "wo cao / wtf"),
    "我靠": ("damn", "damn"),
    "笑死": ("lmao", "laughing to death"),
    "哈哈": ("haha", "haha"),
    "233": ("lol", "233 / lol"),
    "寄": ("we're done for", "ji / doomed"),
    "完了": ("we're done", "it's over"),
    "润": ("run away", "run / bail"),
    "撤": ("retreat", "retreat"),
    "溜了": ("bailing", "bailing"),
    "别送": ("stop feeding", "stop feeding"),
    "送": ("feeding", "feeding / throwing"),
    "带飞": ("carry me", "carry"),
    "大佬": ("pro", "veteran / pro"),
    "萌新": ("newbie", "newbie"),
    "老外": ("foreigner", "foreign player"),
    "卡了": ("lagging", "lagging"),
    "掉线": ("disconnected", "disconnected"),
    "开黑": ("playing together", "queueing together"),
    "牛马": ("grinder", "workhorse"),
}

_PUNCT = re.compile(r"^[\s\W_]+|[\s\W_]+$", re.UNICODE)


def normalize(text: str) -> str:
    s = (text or "").strip().lower()
    s = _PUNCT.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s


def lookup(text: str, target: str):
    """整条消息精确命中时返回 (译文, 源语言)；未命中返回 None。"""
    t = normalize(text)
    base = (target or "").split("-")[0].lower()
    if not t:
        return None
    if t in EN:
        if base == "zh":
            return EN[t][0], "en"
        if base == "en":
            return None, "en"  # 已经是英文，跳过
    if t in ZH:
        if base == "en":
            return ZH[t][0], "zh"
        if base == "zh":
            return None, "zh"
    return None


def prompt_block(limit: int = 60) -> str:
    """给模型的约束 + 词表；控制在几十条，避免 prompt 膨胀。"""
    en_items = list(EN.items())[:limit]
    zh_items = list(ZH.items())[: max(20, limit // 2)]
    en_line = "; ".join(f"{k}={v[1]}" for k, v in en_items)
    zh_line = "; ".join(f"{k}={v[1]}" for k, v in zh_items)
    hd2 = (
        "Helldivers 2 abbreviations: RR=recoilless rifle, EAT=expendable anti-tank, "
        "AC=autocannon, AMR=anti-materiel rifle, HMG=heavy machine gun, "
        "GL=grenade launcher (but 'gl hf' means good luck, have fun), SC=super credits, "
        "FRV=fast recon vehicle, EXO=exosuit, SOS=SOS beacon, 500kg=500kg bomb, "
        "strat=stratagem, evac/extract=extraction, bug=Terminid, bot=Automaton."
    )
    return (
        "Gaming slang and abbreviations: the WHOLE message may be one of these. "
        "Translate the intended meaning, never the letters. "
        f"Examples: {en_line}. Chinese gamer slang: {zh_line}. {hd2} "
        "If an abbreviation is not listed, infer the most common in-game meaning from context "
        "(for example sr/sry=sorry, lol=laughing, gg=good game). "
        "Only keep the original letters when it is a player name, a callsign, or a widely used "
        "term the target players also use (for example GG in Chinese chat)."
    )
