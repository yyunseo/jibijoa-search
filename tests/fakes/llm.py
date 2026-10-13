import hashlib


class FakeMessage:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    """ChatAnthropic 대역. 프롬프트 해시를 기록하고 응답에도 넣어서 프롬프트가 바뀌면 golden이 깨지게 한다."""

    def __init__(self, parse_responses: dict):
        self.parse_responses = parse_responses
        self.prompt_hashes = []

    def invoke(self, messages):
        system = messages[0].content
        human = messages[-1].content if len(messages) > 1 else ""
        digest = hashlib.sha1(f"{system}\n{human}".encode("utf-8")).hexdigest()[:12]
        self.prompt_hashes.append(digest)
        if human.startswith("Analyze the query"):
            for query, response in self.parse_responses.items():
                if query in system:
                    return FakeMessage(response)
            raise AssertionError("준비되지 않은 질의")
        if "You are a Data Analyst" in system:
            return FakeMessage('{"columns": ["gender", "income_household_monthly"]}')
        return FakeMessage(f"요약-{digest}")
