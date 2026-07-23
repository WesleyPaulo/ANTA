"""Testes do modulo de TTS (anta.core.tts).

Cobrem a logica pura e os guards best-effort — sem exigir piper/onnxruntime nem
PortAudio: usamos um sounddevice falso e mockamos urllib.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from anta.core import tts


class TestResolveVoice(unittest.TestCase):
    """Regressao Windows: o Configurador salva a voz como NOME; o runtime aceitava
    so CAMINHO -> 'voz nao encontrada em pt_BR-dii-high'. Agora resolve os dois."""

    def test_none_vira_default(self):
        self.assertEqual(tts._resolve_voice(None), tts.default_voice_path())

    def test_nome_do_catalogo_vira_caminho(self):
        with tempfile.TemporaryDirectory() as d:
            vozes = Path(d)
            (vozes / "pt_BR-dii-high.onnx").write_bytes(b"x")
            with mock.patch.object(tts, "voices_dir", return_value=vozes):
                got = tts._resolve_voice("pt_BR-dii-high")
            self.assertEqual(got, vozes / "pt_BR-dii-high.onnx")

    def test_caminho_completo_existente_passa_direto(self):
        with tempfile.TemporaryDirectory() as d:
            onnx = Path(d) / "minha.onnx"
            onnx.write_bytes(b"x")
            self.assertEqual(tts._resolve_voice(str(onnx)), onnx)

    def test_nome_inexistente_ainda_aponta_pro_voices_dir(self):
        with tempfile.TemporaryDirectory() as d:
            vozes = Path(d)
            with mock.patch.object(tts, "voices_dir", return_value=vozes):
                got = tts._resolve_voice("pt_BR-sumida")
            self.assertEqual(got, vozes / "pt_BR-sumida.onnx")  # exists()=False -> logado


class TestSpeakGuards(unittest.TestCase):
    def test_texto_vazio_noop(self):
        tts.speak("", None)  # nao deve levantar nem tentar sintetizar

    def test_voz_inexistente_noop(self):
        # Voz que nao existe -> no-op silencioso (nem tenta importar piper).
        tts.speak("oi", voice_path="/caminho/que/nao/existe.onnx")


class TestInterrupcao(unittest.TestCase):
    """Botao 'Parar' do HUD: a fala tem que morrer, nao so ser adiada."""

    def tearDown(self):
        tts.reset()  # o Event e de modulo: nao vazar cancelamento entre testes

    def test_stop_marca_e_chama_sd_stop(self):
        fake = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"sounddevice": fake}):
            tts.stop()
        self.assertTrue(tts.cancelled())
        fake.stop.assert_called_once()

    def test_stop_sem_sounddevice_ainda_marca(self):
        # sem PortAudio/sounddevice o audio nem tocava; a marca ainda tem que valer
        with mock.patch.dict(sys.modules, {"sounddevice": None}):
            tts.stop()
        self.assertTrue(tts.cancelled())

    def test_reset_limpa(self):
        tts.stop()
        tts.reset()
        self.assertFalse(tts.cancelled())

    def test_speak_nao_sintetiza_depois_de_parar(self):
        # cancelou antes de comecar: nem chega no piper (evita fala fantasma no fim
        # de um turno que o usuario ja tinha mandado parar)
        with mock.patch.object(tts, "_synthesize") as synth:
            tts.stop()
            tts.speak("oi", voice_path="/qualquer.onnx")
        synth.assert_not_called()

    def test_play_nao_toca_depois_de_parar(self):
        fake = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"sounddevice": fake}):
            tts.stop()
            tts._play(b"\x00\x01", 22050, None)
        fake.play.assert_not_called()


class TestEnsureVoice(unittest.TestCase):
    def test_nao_baixa_se_ja_existe(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            (dest / f"{tts.DEFAULT_VOICE}.onnx").write_bytes(b"modelo")
            (dest / f"{tts.DEFAULT_VOICE}.onnx.json").write_bytes(b"{}")
            with mock.patch("urllib.request.urlopen") as u:
                path = tts.ensure_voice(dest_dir=dest)
                u.assert_not_called()  # arquivos presentes -> sem download
            self.assertEqual(path.name, f"{tts.DEFAULT_VOICE}.onnx")

    def test_baixa_o_que_falta(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            calls = []

            def fake_download(url, target):
                calls.append(url)
                Path(target).write_bytes(b"x")

            with mock.patch.object(tts, "_download", side_effect=fake_download):
                tts.ensure_voice(dest_dir=dest)
            # baixou os dois artefatos (.onnx e .onnx.json)
            self.assertEqual(len(calls), 2)


class TestResolveOutput(unittest.TestCase):
    def _fake_sd(self, devices):
        fake = mock.MagicMock()
        fake.query_devices.return_value = devices
        return mock.patch.dict(sys.modules, {"sounddevice": fake})

    def test_none_quando_vazio(self):
        self.assertIsNone(tts._resolve_output(None))
        self.assertIsNone(tts._resolve_output(""))

    def test_match_exato_saida(self):
        devs = [{"name": "HDA Speakers", "max_output_channels": 2},
                {"name": "USB Mic", "max_output_channels": 0}]
        with self._fake_sd(devs):
            self.assertEqual(tts._resolve_output("HDA Speakers"), 0)

    def test_ignora_entradas(self):
        devs = [{"name": "USB Mic", "max_output_channels": 0},
                {"name": "HDA Speakers", "max_output_channels": 2}]
        with self._fake_sd(devs):
            self.assertIsNone(tts._resolve_output("USB Mic"))


class TestVoiceUrl(unittest.TestCase):
    """Regressao: a base era uma CONSTANTE fixa em pt/pt_BR/faber/medium/, entao
    ensure_voice('pt_BR-cadu-medium') baixava da URL do faber -> 404. So a voz padrao
    funcionava. O layout do repo e derivavel do nome."""

    def test_deriva_do_nome(self):
        self.assertTrue(tts._voice_url("pt_BR-cadu-medium").endswith(
            "/pt/pt_BR/cadu/medium/"))

    def test_outro_idioma(self):
        self.assertTrue(tts._voice_url("en_US-lessac-high").endswith(
            "/en/en_US/lessac/high/"))

    def test_a_voz_padrao_continua_apontando_pro_lugar_certo(self):
        self.assertTrue(tts._voice_url(tts.DEFAULT_VOICE).endswith(
            "/pt/pt_BR/faber/medium/"))

    def test_nome_fora_do_padrao_levanta_com_explicacao(self):
        with self.assertRaises(ValueError) as e:
            tts._voice_url("minha-voz-legal-demais")
        self.assertIn("pt_BR-cadu-medium", str(e.exception))  # diz o formato esperado


class TestImportVoice(unittest.TestCase):
    """O Piper so precisa do par .onnx + .onnx.json — a voz pode vir de qualquer lugar
    (outro repo do HF, um treino seu). Nao ha catalogo fechado."""

    def _voz_falsa(self, d: Path, nome="minha-voz"):
        onnx = d / f"{nome}.onnx"
        onnx.write_bytes(b"MODELO")
        (d / f"{nome}.onnx.json").write_text('{"sample_rate": 22050}', encoding="utf-8")
        return onnx

    def test_importa_arquivo_local_com_o_json_ao_lado(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            onnx = self._voz_falsa(Path(src))
            p = tts.import_voice(onnx, dest_dir=Path(dst))
            self.assertEqual(p.name, "minha-voz.onnx")
            self.assertTrue((Path(dst) / "minha-voz.onnx.json").exists())
            self.assertEqual(p.read_bytes(), b"MODELO")

    def test_nome_pode_ser_renomeado(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            onnx = self._voz_falsa(Path(src))
            p = tts.import_voice(onnx, nome="wesley", dest_dir=Path(dst))
            self.assertEqual(p.name, "wesley.onnx")
            self.assertTrue((Path(dst) / "wesley.onnx.json").exists())

    def test_sem_o_json_nao_deixa_voz_pela_metade(self):
        # o .json traz fonemas/sample_rate: sem ele o Piper nao carrega. Falhar aqui e
        # melhor do que uma voz que so quebra na hora de falar.
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            onnx = Path(src) / "so-o-modelo.onnx"
            onnx.write_bytes(b"MODELO")
            with self.assertRaises(FileNotFoundError):
                tts.import_voice(onnx, dest_dir=Path(dst))
            self.assertEqual(list(Path(dst).iterdir()), [])  # nao sobrou lixo

    def test_arquivo_inexistente_levanta(self):
        with tempfile.TemporaryDirectory() as dst:
            with self.assertRaises(FileNotFoundError):
                tts.import_voice("/nao/existe.onnx", dest_dir=Path(dst))

    def test_url_usa_download(self):
        baixados = []
        with tempfile.TemporaryDirectory() as dst:
            def fake_download(url, dest):
                baixados.append(url)
                dest.write_bytes(b"x")
            with mock.patch.object(tts, "_download", fake_download):
                tts.import_voice("https://ex.com/v/dii.onnx", dest_dir=Path(dst))
        self.assertEqual(baixados,
                         ["https://ex.com/v/dii.onnx", "https://ex.com/v/dii.onnx.json"])


class TestCatalogoPt(unittest.TestCase):
    def test_nomes_do_catalogo_geram_url_valida(self):
        for nome in tts.VOZES_PT:
            self.assertTrue(tts._voice_url(nome).startswith("https://"), nome)

    def test_nao_inventa_genero(self):
        # NENHUMA fonte (voices.json, MODEL_CARDs, cards da comunidade) tem campo de
        # genero; deduzir pelo nome do speaker e chute — ja chutei uma vez. O que da pra
        # afirmar e o F0 medido, que e registro, nao genero.
        texto = (" ".join(tts.VOZES_PT.values())
                 + " " + " ".join(d for _u, d in tts.VOZES_COMUNIDADE.values())).lower()
        for palavra in ("masculina", "feminina", "masculino", "feminino"):
            self.assertNotIn(palavra, texto)

    def test_comunidade_tem_url_propria(self):
        # sem URL, `anta vozes pt_BR-dii-high` cairia no ensure_voice -> 404 no repo
        # oficial (a voz nao esta la). Por isso o mapa guarda a URL.
        for nome, (url, _desc) in tts.VOZES_COMUNIDADE.items():
            self.assertTrue(url.startswith("https://"), nome)
            self.assertTrue(url.endswith(".onnx"), nome)
            self.assertNotIn(nome, tts.VOZES_PT)  # senao o catalogo venceria no CLI

    def test_licenca_indeterminada_e_sinalizada(self):
        # os repos da comunidade nao declaram licenca; nao esconder isso do usuario
        for nome, (_url, desc) in tts.VOZES_COMUNIDADE.items():
            self.assertIn("licenca", desc.lower(), nome)


if __name__ == "__main__":
    unittest.main()
