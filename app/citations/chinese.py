"""中文词法支撑判定（I6）：rules.py 的并行输入处理层。

红线4 约束下的设计：本模块不修改 rules.py 的任何函数与判定语义，
只把 tokenizer 换成中英混合口径（英文词 + 中文单字/bigram）、否定
检测换成中文词表、并增加数字锚点校验；判定结构（r1 精确包含 /
r2 重叠阈值 / r6 否定冲突）与阈值（SOURCE_POLICY）原样镜像。

启用条件：ENABLE_CITATION_VALIDATION 与 CITATIONS_CHINESE_TOKENIZER
同时为真（runtime_adapter 负责串联）。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from app.citations.rules import SOURCE_POLICY, SourceKind, Verdict

CHINESE_TOKENIZER_ENV = "CITATIONS_CHINESE_TOKENIZER"

_ENGLISH_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CJK_SEGMENT_RE = re.compile(r"[\u4e00-\u9fff]+")
_DIGIT_RE = re.compile(r"\d+(?:\.\d+)?")
# 中文否定词表：词组为主，避免"不/未/无"单字在"不断/未来/无效"中的误报
_CHINESE_NEGATIONS = (
    "不会",
    "不能",
    "不可以",
    "不得",
    "不许",
    "不允",
    "没有",
    "并未",
    "并非",
    "禁止",
    "严禁",
    "无权",
    "勿",
)

_TRUE_VALUES = {"1", "true", "yes", "on"}


def chinese_enabled(environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return env.get(CHINESE_TOKENIZER_ENV, "").strip().casefold() in _TRUE_VALUES


def tokenize_chinese(text: str) -> tuple[str, ...]:
    """英文按词、中文按单字+相邻 bigram 切分（与 qdrant_local 词法同构）。"""
    folded = text.casefold()
    tokens: list[str] = list(_ENGLISH_TOKEN_RE.findall(folded))
    for segment in _CJK_SEGMENT_RE.findall(folded):
        tokens.extend(segment)
        tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
    return tuple(tokens)


def _digits(text: str) -> set[str]:
    """数字锚点集合：按数值归一（023 与 23 同值），小数原样保留。"""
    values: set[str] = set()
    for raw in _DIGIT_RE.findall(text):
        try:
            values.add(str(int(raw)))
        except ValueError:
            values.add(raw)
    return values


def _negations(text: str) -> set[str]:
    found: set[str] = set()
    for negation in _CHINESE_NEGATIONS:
        if negation in text:
            found.add(negation)
    return found


@dataclass(frozen=True)
class ChineseJudgment:
    verdict: Verdict
    score: float
    matched: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)


def check_chinese(claim: dict, evidence: dict) -> ChineseJudgment:
    """镜像 rules.check 的判定语义，输入处理层为中文口径。

    判定顺序：空声明 → r6 否定冲突 → 数字锚点 → r1 精确包含 →
    r2 重叠阈值。全部只读，不触碰 rules.py。
    """
    statement = str(claim.get("statement") or "").strip()
    quote = str(evidence.get("quote") or "")
    source_kind = str(evidence.get("source_kind") or "knowledge")
    try:
        min_overlap = SOURCE_POLICY[SourceKind(source_kind)].min_overlap
    except KeyError:
        min_overlap = SOURCE_POLICY[SourceKind.KNOWLEDGE].min_overlap

    if not statement:
        return ChineseJudgment(
            Verdict.UNSUPPORTED,
            0.0,
            reasons=("声明为空，无法判定（中文路径）",),
        )

    claim_negations = _negations(statement)
    quote_negations = _negations(quote)
    new_negations = sorted(quote_negations - claim_negations)
    if new_negations:
        return ChineseJudgment(
            Verdict.CONTRADICTED,
            0.0,
            reasons=(
                "证据原文引入了声明中不存在的否定表述："
                + "、".join(new_negations)
                + "（r6 否定冲突，中文路径）",
            ),  # 尾逗号：单元素 tuple（I6 修正：缺逗号实为 str，迭代会逐字符展开）
        )

    claim_digits = _digits(statement)
    quote_digits = _digits(quote)
    missing_digits = sorted(claim_digits - quote_digits)
    if missing_digits:
        return ChineseJudgment(
            Verdict.UNSUPPORTED,
            0.0,
            reasons=(
                "声明中的数字 "
                + "、".join(missing_digits)
                + " 未出现在证据原文中（数字锚点，中文路径）",
            ),  # 尾逗号：单元素 tuple
        )

    claim_tokens = set(tokenize_chinese(statement))
    quote_tokens = set(tokenize_chinese(quote))
    matched = tuple(sorted(claim_tokens & quote_tokens))
    score = len(matched) / len(claim_tokens) if claim_tokens else 0.0

    normalized_statement = re.sub(r"\s+", "", statement)
    normalized_quote = re.sub(r"\s+", "", quote)
    if normalized_statement in normalized_quote:
        return ChineseJudgment(
            Verdict.SUPPORTED,
            1.0,
            matched,
            reasons=("声明是证据原文的精确片段（r1 精确包含，中文路径）",),
        )

    if score >= min_overlap:
        return ChineseJudgment(
            Verdict.SUPPORTED,
            score,
            matched,
            reasons=(
                f"token 重叠率 {score:.2f} 达到 {min_overlap:.2f} 阈值"
                "（r2 词法重叠，中文路径）",
            ),  # 尾逗号：单元素 tuple
        )
    return ChineseJudgment(
        Verdict.UNSUPPORTED,
        score,
        matched,
        reasons=(
            f"token 重叠率 {score:.2f} 低于 {min_overlap:.2f} 阈值"
            "（r2 词法重叠，中文路径）",
        ),  # 尾逗号：单元素 tuple
    )


__all__ = [
    "CHINESE_TOKENIZER_ENV",
    "ChineseJudgment",
    "Verdict",
    "check_chinese",
    "chinese_enabled",
    "tokenize_chinese",
]
