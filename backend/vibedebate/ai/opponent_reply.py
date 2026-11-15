from secrets import token_hex

from vibedebate.ai.contracts import AIChunk


def victory_marker() -> str:
    return f"[[VD_VICTORY_{token_hex(16)}]]"


class OpponentChunk(AIChunk):
    user_victory: bool = False


class OpponentReplyFilter:
    """Keep a split control footer out of visible text; accept only a final footer."""

    def __init__(self, marker: str | None):
        self.marker = "\n" + marker if marker else None
        self.buffer = ""
        self.control_started = False
        self.control_token = ""
        self.valid_boundary = False

    def feed(self, delta: str) -> str:
        if self.marker is None:
            return delta

        self.buffer += delta
        if self.control_started:
            return ""

        # Also hide a malformed current token without its required line boundary.
        tokens = (self.marker, self.marker[1:])
        for token in tokens:
            position = self.buffer.find(token)
            if position >= 0:
                visible, self.buffer = self.buffer[:position], self.buffer[position:]
                self.control_started = True
                self.control_token = token
                self.valid_boundary = token == self.marker
                return visible

        keep = 0
        for token in tokens:
            for length in range(1, min(len(self.buffer), len(token)) + 1):
                if self.buffer.endswith(token[:length]):
                    keep = max(keep, length)

        visible = self.buffer[:-keep] if keep else self.buffer
        self.buffer = self.buffer[-keep:] if keep else ""
        return visible

    def finish(self) -> tuple[str, bool]:
        if self.marker and self.control_started:
            if self.valid_boundary and self.buffer.rstrip() == self.control_token:
                return "", True
            return self.buffer[len(self.control_token) :], False

        # An incomplete control prefix cannot award victory or leak a partial token.
        if self.marker and (
            self.buffer.startswith("\n[[") or self.buffer.startswith("[[VD_")
        ):
            return "", False
        return self.buffer, False
