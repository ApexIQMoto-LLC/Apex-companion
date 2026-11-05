"""Bounded wake-and-conversation state machine; no audio or paid calls here."""
from __future__ import annotations

import re
import time

DEFAULT_WAKE_PHRASES = (
    "apex open apex", "apex start apex", "open apex", "start apex",
    "hey apex", "apex", "hey jarvis",
    # Vosk small English often splits the uncommon name "Apex" into two words.
    # Only whole phrase prefixes are accepted; this never fuzzily matches
    # arbitrary text or the product name ApexIQ.
    "hey a pecks", "hey a packs", "hey a pecs", "hey a pex",
    "a pecks", "a packs", "a pecs", "a pex",
    "open a pecks", "open a packs", "start a pecks", "start a packs",
)
SLEEP_PHRASES = frozenset((
    "go to sleep", "sleep apex", "stop listening", "close apex", "goodbye apex",
    "that's all apex", "thats all apex", "end conversation",
))


def normalized_words(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s']+", " ", str(text).lower()).split())


def wake_remainder(text: str, phrases=DEFAULT_WAKE_PHRASES):
    """Return (wake_detected, command_after_wake), at word boundaries only."""
    value = normalized_words(text)
    for phrase in sorted((normalized_words(p) for p in phrases if p), key=len, reverse=True):
        if value == phrase:
            return True, ""
        if value.startswith(phrase + " "):
            rest = value[len(phrase):].strip()
            for opener in ("open apex", "start apex"):
                if rest == opener:
                    rest = ""
                elif rest.startswith(opener + " "):
                    rest = rest[len(opener):].strip()
            return True, rest
    return False, ""


class ConversationSession:
    """After wake, accept natural follow-up speech until a bounded idle timeout."""
    def __init__(self, phrases=DEFAULT_WAKE_PHRASES, idle_seconds=120, clock=None):
        self.phrases = tuple(phrases)
        self.idle_seconds = max(15, min(600, int(idle_seconds)))
        self.clock = clock or time.monotonic
        self.expires_at = 0.0
        self.mode = "general"

    @property
    def active(self):
        return self.clock() < self.expires_at

    def activate(self, mode="general"):
        self.expires_at = self.clock() + self.idle_seconds
        if mode in {"business", "personal", "general"}:
            self.mode = mode

    def close(self):
        self.expires_at = 0.0

    def accept(self, text: str):
        """Return (wake|utterance|sleep|ignore, content). Never executes commands."""
        text = normalized_words(text)
        if not text:
            return "ignore", ""
        if self.active and text in SLEEP_PHRASES:
            self.close()
            return "sleep", ""
        woke, command = wake_remainder(text, self.phrases)
        if woke:
            if command in SLEEP_PHRASES:
                self.close()
                return "sleep", ""
            self.activate(self.mode)
            return ("utterance", command) if command else ("wake", "")
        if self.active:
            self.activate(self.mode)
            return "utterance", text
        return "ignore", ""


BUSINESS_START_QUESTION = (
    "I'm ready to talk business. Should we focus on beta riders, "
    "marketing content, Replay Studio growth, or revenue?"
)
PERSONAL_START_QUESTION = (
    "I'm here. Do you want to talk about your goals, plan your day, "
    "or discuss something on your mind?"
)
DEFAULT_START_QUESTION = (
    "I'm here. Do you want to talk business, work on Replay Studio, "
    "or discuss something personal?"
)


def opening_question(mode: str) -> str:
    return (BUSINESS_START_QUESTION if mode == "business" else
            PERSONAL_START_QUESTION if mode == "personal" else DEFAULT_START_QUESTION)


def conversational_instructions(mode="general"):
    """Extra model instructions for user-initiated, turn-taking spoken dialogue."""
    topic = (
        "Prioritize ApexIQ Moto marketing, hardware beta acquisition, creator partners, "
        "Replay Studio promotion, product operations, and measurable ROI."
        if mode == "business" else
        "Focus on the user's personal goals and requested support, without accessing "
        "private domains unless authorized."
        if mode == "personal" else
        "Follow the topic the user raises; distinguish business and personal contexts."
    )
    return (
        "VOICE CONVERSATION MODE. Sound like a trusted, quick-thinking human collaborator, "
        "not a customer-support bot or a formal report. Use contractions and natural wording, "
        "typically 1-3 sentences, under 70 spoken words. Give a concrete helpful answer "
        "before asking at most one useful follow-up question. Never add a generic final question "
        "by habit. If the transcript has garbled words or obvious recognition errors, infer "
        "intent cautiously from recent dialogue, and ask a short clarifying question only "
        "when necessary. Do not latch onto random phrases or insist the user meant them. "
        "When discussing content, actively suggest a specific hook, quick-cut shot sequence, "
        "and CTA instead of merely offering options. Refer to the user's current business "
        "project naturally, not with repetitive promotional language. "
        "Use conversation history and authorized read-only tools when relevant; "
        "be truthful about unconnected social accounts and unavailable live analytics. "
        "Don't invent business numbers, actions, account connections or successful edits. "
        "Avoid Markdown tables, links and long lists in speech. " + topic
    )
