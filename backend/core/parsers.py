from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class SafeJSONParser(JSONParser):
    """Reject JSON that exceeds the decoder's recursion limit as client input."""

    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return super().parse(stream, media_type=media_type, parser_context=parser_context)
        except RecursionError:
            raise ParseError("JSON parse error.") from None
