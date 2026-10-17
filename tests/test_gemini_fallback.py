from types import SimpleNamespace

from gemini_analysis import _generate_with_fallback


class ApiError(Exception):
    def __init__(self, code, message='API error'):
        super().__init__(message)
        self.code = code


def test_rate_limit_tries_configured_fallback_model(monkeypatch):
    monkeypatch.setenv('GEMINI_MODEL', 'primary-model')
    monkeypatch.setenv('GEMINI_FALLBACK_MODELS', 'backup-model,backup-lite')
    calls = []

    class FakeModels:
        def generate_content(self, model, contents):
            calls.append(model)
            if model == 'primary-model':
                raise ApiError(429, 'RESOURCE_EXHAUSTED')
            return SimpleNamespace(text='ranked response')

    client = SimpleNamespace(models=FakeModels())
    response, model, errors = _generate_with_fallback(client, 'prompt')

    assert calls == ['primary-model', 'backup-model']
    assert response.text == 'ranked response'
    assert model == 'backup-model'
    assert errors[0][0] == 'primary-model'


def test_non_retryable_error_does_not_call_fallback(monkeypatch):
    monkeypatch.setenv('GEMINI_MODEL', 'primary-model')
    monkeypatch.setenv('GEMINI_FALLBACK_MODELS', 'backup-model')
    calls = []

    class FakeModels:
        def generate_content(self, model, contents):
            calls.append(model)
            raise ApiError(403, 'permission denied')

    client = SimpleNamespace(models=FakeModels())
    response, model, errors = _generate_with_fallback(client, 'prompt')

    assert response is None
    assert model is None
    assert calls == ['primary-model']
    assert errors[0][1].code == 403
