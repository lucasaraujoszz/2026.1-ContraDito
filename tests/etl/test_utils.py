import pytest
from unittest.mock import MagicMock, patch
from utils.cleaner import limpar_texto_discurso
from utils.motor_nlp import MotorNLP


def test_limpar_texto_discurso():
    assert limpar_texto_discurso(None) == ""
    assert limpar_texto_discurso("") == ""

    # Remove tags HTML
    assert limpar_texto_discurso("<p>Olá</p>") == "Olá"

    # Remove prefixo de orador
    assert limpar_texto_discurso("O SR. JOÃO (PL-SP) - Olá") == "Olá"

    # Remove reações e notas taquigráficas em parênteses e colchetes
    assert limpar_texto_discurso("Discurso [palmas] (risos)") == "Discurso"

    # Remove jargões inúteis (mantendo pontuações residuais)
    assert limpar_texto_discurso("Sr. Presidente, peço a palavra") == ","


@pytest.mark.asyncio
@patch("utils.motor_nlp.SentenceTransformer")
async def test_motor_nlp(mock_transformer):
    mock_model = MagicMock()
    # Mock do retorno para simular um objeto com método tolist() (como arrays do NumPy)
    mock_vector = MagicMock()
    mock_vector.tolist.return_value = [0.1, 0.2, 0.3]
    mock_model.encode.return_value = mock_vector
    mock_transformer.return_value = mock_model

    motor = MotorNLP()

    # Entrada vazia
    assert await motor.gerar_embedding("") == []

    # Entrada válida
    res = await motor.gerar_embedding("Texto de teste")
    assert res == [0.1, 0.2, 0.3]
