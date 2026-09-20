"""Testes das regras da live. Rodam sozinhos, sem rede e sem Roblox.

    python ponte\\testes.py

(ou, mais facil, pelo TESTAR-TUDO.bat, que roda esta suite junto com a do
enquadramento da camera.)

POR QUE ESTES TESTES EXISTEM

As regras de presente sao a parte do kit em que um erro nao levanta excecao
nenhuma: ele so' faz a rosa ficar do tamanho da galaxia. Ninguem percebe
olhando o codigo, e quem percebe e' o espectador que pagou 1000 moedas e viu o
mesmo efeito de quem pagou 1.

Cada teste aqui e' uma afirmacao sobre o PRODUTO, e nao sobre a implementacao:
"presente mais caro tem que crescer mais", "presente que nunca foi cadastrado
tem que funcionar mesmo assim", "curtida nao pode furar a fila".
"""

import json
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, "servidor"))

import nicks     # noqa: E402
import painel    # noqa: E402
import regras    # noqa: E402
import servidor  # noqa: E402


class ConfigDeMentira(painel.ConfigDoPainel):
    """A ConfigDoPainel sem rede: recebe o dicionario pronto."""

    def __init__(self, dados):
        super().__init__("", "")
        self._cfg = dados
        self._versao = 1


# ══════════════════════════════════════════════════════════════════
#  A ESCADA DOS PRESENTES
# ══════════════════════════════════════════════════════════════════

class TesteEscadaDosPresentes(unittest.TestCase):
    """Presente mais caro tem que fazer mais coisa. Sempre."""

    def test_faixas_de_preco_sobem_junto_com_o_valor(self):
        anterior = None
        for moedas in (1, 10, 30, 200, 1000):
            e = regras.efeito_do_presente("presente que ninguem cadastrou", moedas)
            if anterior is not None:
                self.assertGreaterEqual(
                    e["crescimento"], anterior["crescimento"],
                    f"o presente de {moedas} moedas cresce MENOS que o anterior")
                self.assertGreaterEqual(
                    e["prio"], anterior["prio"],
                    f"o presente de {moedas} moedas tem prioridade MENOR")
            anterior = e

    def test_presente_desconhecido_nunca_fica_sem_efeito(self):
        """A rede de seguranca por preco. E' o que faz o kit funcionar com um
        presente que o TikTok lancou ontem, sem cadastro nenhum."""
        e = regras.efeito_do_presente("Presente Inventado Ontem", 500)
        self.assertGreater(e["escala"], 1.0)
        self.assertGreater(e["crescimento"], 0)
        self.assertGreater(e["prio"], 0)

    def test_os_quatro_presentes_do_kit_tem_efeitos_distintos(self):
        vistos = {}
        for nome in ("rose", "doughnut", "sunglasses", "galaxy"):
            e = regras.efeito_do_presente(nome, 1)
            vistos[nome] = (e["escala"], e["crescimento"], e["danca"])
        self.assertEqual(len(set(vistos.values())), 4,
                         f"dois presentes com o MESMO efeito: {vistos}")

    def test_combo_nao_muda_a_faixa_do_presente(self):
        """Dez rosas de 1 moeda continuam sendo rosas.

        Tratar o total do combo como valor unitario transformaria dez rosinhas
        num presente de outra faixa -- e o espectador que gastou 10 moedas
        receberia o efeito de quem gastou 10 de uma vez so'.
        """
        uma = regras.efeito_do_presente("rose", 1)
        dez = regras.efeito_do_presente("rose", 1, total_combo=10)
        self.assertEqual(uma["escala"], dez["escala"])
        self.assertEqual(uma["crescimento"], dez["crescimento"])
        # So' a prioridade sobe: combo maior fura mais a fila.
        self.assertGreater(dez["prio"], uma["prio"])

    def test_nenhum_efeito_passa_dos_tetos(self):
        """Um painel editado na mao nao pode gerar um avatar que quebra a live."""
        louco = {"escala": 999, "crescimento": 999, "segura": 999, "cena": 999,
                 "chuva": 999, "furacao": 999, "prio": 999, "brilho": 99,
                 "colosso": 999, "danca_geral": 9999}
        e = regras.limitar(louco)
        self.assertLessEqual(e["escala"], regras.ESCALA_MAX)
        self.assertLessEqual(e["crescimento"], regras.CRESCIMENTO_MAX)
        self.assertLessEqual(e["segura"], regras.SEGURA_MAX)
        self.assertLessEqual(e["chuva"], regras.CHUVA_MAX)
        self.assertLessEqual(e["furacao"], regras.FURACAO_MAX)
        self.assertLessEqual(e["brilho"], regras.BRILHO_MAX)

    def test_efeito_torto_vira_efeito_completo(self):
        """O resto da ponte espera TODOS os campos. Um efeito vindo do painel
        com metade das chaves quebraria em outro lugar, longe daqui."""
        e = regras.limitar({"escala": 2})
        for campo in ("prio", "escala", "crescimento", "vida", "segura", "cena",
                      "furacao", "chuva", "cor", "brilho", "danca",
                      "danca_geral", "colosso"):
            self.assertIn(campo, e)

    def test_danca_desconhecida_vira_a_padrao(self):
        """O Roblox NAO reclama de uma animacao que nao existe: ela carrega, o
        Play() funciona, e o boneco fica parado em pe'. Barrar aqui e' o unico
        ponto do caminho em que da' pra perceber o erro."""
        self.assertEqual(regras.limitar({"danca": "nao_existe"})["danca"], "")
        self.assertEqual(regras.limitar({"danca": "galaxia"})["danca"], "galaxia")


# ══════════════════════════════════════════════════════════════════
#  O PAINEL MANDA NO JOGO
# ══════════════════════════════════════════════════════════════════

class TestePainelMandaNoJogo(unittest.TestCase):
    """O pedido central do produto: o que esta' no painel e' o que acontece."""

    def setUp(self):
        self.cfg = ConfigDeMentira({
            "presentes": {
                "rose": {"escala": 1.5, "crescimento": 0.25, "prio": 2,
                         "id": "5655", "grupo": "rosa"},
                "rosa": {"escala": 1.5, "crescimento": 0.25, "prio": 2,
                         "id": "5655", "grupo": "rosa"},
                "galaxy": {"escala": 3.2, "crescimento": 1.6, "prio": 6,
                           "id": "6064", "grupo": "galaxia"},
            },
            "faixas": [
                {"min": 1000, "efeito": {"escala": 3.0, "crescimento": 1.5, "prio": 6}},
                {"min": 1, "efeito": {"escala": 1.0, "crescimento": 0.1, "prio": 2}},
            ],
            "acoes": {},
            "geral": {"tamanho_max": 8.0, "crescimento_suave": 0.9},
        })

    def test_valor_do_painel_vence_a_tabela_de_fabrica(self):
        e = self.cfg.efeito_do_presente("rose", 1)
        self.assertEqual(e["escala"], 1.5)
        self.assertEqual(e["crescimento"], 0.25)

    def test_casa_por_id_quando_o_nome_chega_de_outra_regiao(self):
        """O nome do presente muda de pais pra pais; o ID nao.

        E' o caso concreto de uma live com audiencia de fora: o presente chega
        como "Rosa" pra uns e "Rose" pra outros, e um terceiro nome numa
        terceira regiao. Pelo ID, todos recebem o mesmo efeito.
        """
        e = self.cfg.efeito_do_presente("UmNomeQueNinguemCadastrou", 1,
                                        presente_id="5655")
        self.assertEqual(e["escala"], 1.5)
        self.assertEqual(e["crescimento"], 0.25)

    def test_id_vence_o_apelido(self):
        """Se os dois casarem em fichas diferentes, o ID manda -- ele e' o
        identificador confiavel."""
        e = self.cfg.efeito_do_presente("rose", 1, presente_id="6064")
        self.assertEqual(e["escala"], 3.2, "o ID deveria ter vencido o nome")

    def test_id_em_formatos_diferentes_casa_igual(self):
        """O mesmo ID chega como inteiro, como float e como texto no caminho."""
        for forma in ("5655", 5655, 5655.0):
            e = self.cfg.efeito_do_presente("qualquer", 1, presente_id=forma)
            self.assertEqual(e["escala"], 1.5, f"nao casou com o ID {forma!r}")

    def test_sem_cadastro_cai_na_faixa_do_painel(self):
        e = self.cfg.efeito_do_presente("Presente Novo", 2000)
        self.assertEqual(e["escala"], 3.0)
        self.assertEqual(e["crescimento"], 1.5)

    def test_painel_fora_do_ar_cai_na_tabela_de_fabrica(self):
        """Nunca e' o painel que decide se a live FUNCIONA; so' o quanto ela
        e' sua."""
        vazio = ConfigDeMentira(None)
        e = vazio.efeito_do_presente("galaxy", 1000)
        self.assertEqual(e["escala"], regras.LENDARIO["escala"])
        self.assertEqual(e["crescimento"], regras.LENDARIO["crescimento"])

    def test_ajustes_de_crescimento_chegam_como_decimal(self):
        """O `geral()` inteiro transformaria 0.9s de animacao em ZERO -- o
        crescimento suave viraria um salto seco e o ajuste do painel pareceria
        nao funcionar."""
        self.assertEqual(self.cfg.geral_decimal("crescimento_suave", 0.6), 0.9)
        self.assertEqual(self.cfg.geral_decimal("tamanho_max", 6.0), 8.0)

    def test_acao_desligada_no_painel_nao_spawna(self):
        cfg = ConfigDeMentira({
            "acoes": {"curtida": {"ativo": False}, "comentario": {"ativo": True}},
        })
        efeito, _ = cfg.efeito_curtida()
        self.assertIsNone(efeito, "curtida desligada nao pode spawnar")
        self.assertIsNotNone(cfg.efeito_do_comentario())

    def test_na_duvida_a_curtida_fica_DESLIGADA(self):
        """Sem painel, a curtida NAO spawna.

        E' a correcao de um defeito que aparecia ao vivo: no primeiro soluco de
        rede a curtida voltava a spawnar sozinha, e como curtida nao aparece no
        chat, quem estava transmitindo via bonecos nascendo do nada.
        """
        efeito, _ = ConfigDeMentira(None).efeito_curtida()
        self.assertIsNone(efeito)

    def test_na_duvida_o_comentario_fica_LIGADO(self):
        """Comentario com nick e' A promessa do kit: falhar fechado nele
        deixaria a live muda, que e' o defeito oposto e igualmente ruim."""
        self.assertIsNotNone(ConfigDeMentira(None).efeito_do_comentario())


# ══════════════════════════════════════════════════════════════════
#  O LIMITADOR DE TAXA
# ══════════════════════════════════════════════════════════════════

class TesteLimitadorDeTaxa(unittest.TestCase):
    """So' presente fura a fila. Foi um bug de verdade: curtida tem prio 1, e a
    regra antiga (`prio > 0`) deixava ela passar como se fosse paga."""

    def novoTradutor(self):
        import ponte
        return ponte.Tradutor("", "", simular_envio=True)

    def evento(self, tipo, prio):
        return {"tipo": tipo, "prio": prio, "nickname": "x", "roblox_id": 1,
                "escala": 1, "segura": 0}

    def test_presente_passa_sempre(self):
        t = self.novoTradutor()
        presentes = [self.evento("presente", 5) for _ in range(20)]
        escolhidos = t.escolher(presentes)
        self.assertEqual(len(escolhidos), 20,
                         "presente foi pago: nao pode ser barrado por orcamento")

    def test_curtida_NAO_fura_a_fila(self):
        t = self.novoTradutor()
        curtidas = [self.evento("curtida", 1) for _ in range(50)]
        escolhidos = t.escolher(curtidas)
        self.assertLess(len(escolhidos), 10,
                        "curtida passou pelo teto de taxa -- era o bug antigo")

    def test_seguiu_e_compartilhou_tambem_nao_furam(self):
        t = self.novoTradutor()
        eventos = [self.evento("seguiu", 2) for _ in range(50)]
        self.assertLess(len(t.escolher(eventos)), 10)

    def test_o_que_sobra_vai_pro_mais_valioso(self):
        """Com o orcamento apertado, um "seguiu" (raro) nao pode perder a vaga
        pra dois comentarios que chegaram depois dele."""
        t = self.novoTradutor()
        t.credito = 1.0
        eventos = [self.evento("seguiu", 2),
                   self.evento("comentario", 0),
                   self.evento("comentario", 0)]
        escolhidos = t.escolher(eventos, dt=0)
        self.assertEqual(len(escolhidos), 1)
        self.assertEqual(escolhidos[0]["tipo"], "seguiu")


# ══════════════════════════════════════════════════════════════════
#  A LEITURA DO NICK NO CHAT
# ══════════════════════════════════════════════════════════════════

class TesteLeituraDeNick(unittest.TestCase):

    def test_comentario_de_uma_palavra_e_o_caso_comum(self):
        self.assertEqual(nicks.achar_nick("builderman"), "builderman")
        self.assertEqual(nicks.achar_nick("  Player_123  "), "Player_123")

    def test_frase_com_aviso(self):
        self.assertEqual(nicks.achar_nick("meu nick e Fulano123"), "Fulano123")
        self.assertEqual(nicks.achar_nick("nick: Beltrano"), "Beltrano")

    def test_conversa_de_chat_nao_vira_avatar(self):
        """Mostrar o avatar de um ESTRANHO porque alguem escreveu uma palavra
        comum e' o erro mais caro deste modulo: "que", "esse", "onde" e "vez"
        sao todas contas reais no Roblox."""
        for texto in ("kkkkk", "oi", "que", "esse", "onde", "vez", "bora",
                      "top", "muito bom", "eu quero"):
            self.assertIsNone(nicks.achar_nick(texto),
                              f"{texto!r} nao deveria virar nick")

    def test_emoji_nas_bordas_nao_estraga_o_nick(self):
        self.assertEqual(nicks.achar_nick("Player123!!!"), "Player123")

    def test_formato_invalido_e_recusado(self):
        for texto in ("ab", "_comeca_com_underscore", "termina_", "a" * 30):
            self.assertIsNone(nicks.achar_nick(texto), f"{texto!r} passou")


# ══════════════════════════════════════════════════════════════════
#  OS AJUSTES NO DISCO
# ══════════════════════════════════════════════════════════════════

class TesteAjustes(unittest.TestCase):

    def test_presentes_e_SUBSTITUIDO_e_nao_mesclado(self):
        """E' o que faz DESLIGAR um presente funcionar. Com a mesclagem normal,
        "sumiu" nao quer dizer nada -- o valor antigo continuaria pra sempre."""
        base = {"presentes": {"rose": {"escala": 1}, "galaxy": {"escala": 3}}}
        novo = {"presentes": {"rose": {"escala": 2}}}
        fora = servidor._mesclar(base, novo)
        self.assertEqual(list(fora["presentes"]), ["rose"])
        self.assertEqual(fora["presentes"]["rose"]["escala"], 2)

    def test_outras_secoes_sao_mescladas_chave_a_chave(self):
        """O painel manda so' o pedaco que ele conhece, e um update raso
        apagaria o resto."""
        base = {"geral": {"por_fila": 10, "total_avatares": 100}}
        fora = servidor._mesclar(base, {"geral": {"por_fila": 5}})
        self.assertEqual(fora["geral"]["por_fila"], 5)
        self.assertEqual(fora["geral"]["total_avatares"], 100)

    def test_arquivo_antigo_ganha_os_campos_novos(self):
        """Quem ATUALIZOU o kit nao pode ficar com presentes que nao crescem."""
        antigo = {"presentes": {
            "rose": {"prio": 2, "escala": 1.0, "segura": 1.0, "cor": "FF9EC4"},
        }}
        migrado = servidor._migrar(servidor._mesclar(servidor.AJUSTES_PADRAO, antigo))
        rose = migrado["presentes"]["rose"]
        self.assertIn("crescimento", rose)
        self.assertGreater(rose["crescimento"], 0)
        self.assertEqual(rose["grupo"], "rosa")
        self.assertEqual(rose["rotulo"], "Rosa")

    def test_valor_acima_do_teto_e_cortado_na_LEITURA(self):
        """O caso real: o oculos ficou gravado com escala 10, o painel mostrava
        10, e o jogo desenhava 4 -- porque o teto do motor e' 4. O painel virava
        um mentiroso."""
        salvo = {"presentes": {"sunglasses": {"escala": 10, "prio": 5}}}
        migrado = servidor._migrar(servidor._mesclar(servidor.AJUSTES_PADRAO, salvo))
        self.assertEqual(migrado["presentes"]["sunglasses"]["escala"],
                         regras.ESCALA_MAX)

    def test_identidade_do_presente_sobrevive_a_normalizacao(self):
        """O `limitar` so' conhece campos de efeito. Se ele passasse por cima
        do nome e do ID, salvar o painel apagaria o cadastro."""
        e = servidor._normalizar_efeito({
            "escala": 2, "grupo": "rosa", "rotulo": "Rosa", "id": "5655",
            "moedas": 1, "apelidos": ["rose", "rosa"], "emoji": "R"})
        self.assertEqual(e["grupo"], "rosa")
        self.assertEqual(e["id"], "5655")
        self.assertEqual(e["apelidos"], ["rose", "rosa"])

    def test_arquivo_corrompido_nao_impede_a_live_de_subir(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            f.write("{ isto nao e' json valido")
            caminho = f.name
        try:
            a = servidor.Ajustes(caminho)
            self.assertIn("presentes", a.ler())
        finally:
            os.unlink(caminho)


# ══════════════════════════════════════════════════════════════════
#  O CONTRATO COM O ROBLOX
# ══════════════════════════════════════════════════════════════════

class TesteContratoComORoblox(unittest.TestCase):

    def test_o_spawn_leva_tudo_que_o_jogo_le(self):
        """Se um campo sumir daqui, o jogo cai no valor padrao dele -- sem erro
        nenhum, e com o presente fazendo outra coisa."""
        spawn = regras.montar_spawn(
            "id1", "Fulano", 156, regras.limitar(regras.GRANDE), 30,
            nick_roblox="builderman", presente="Doughnut", tipo="presente",
            presente_id="1234")
        for campo in ("tiktok_id", "nickname", "nick_roblox", "roblox_id",
                      "prio", "escala", "crescimento", "vida", "segura", "cena",
                      "furacao", "cor", "brilho", "danca", "danca_geral",
                      "colosso", "presente", "presente_id", "moedas", "tipo",
                      "curtidas", "combo"):
            self.assertIn(campo, spawn, f"o campo {campo} sumiu do spawn")

    def test_o_spawn_e_serializavel_em_json(self):
        """Ele viaja por HTTP ate' o Roblox. Um valor que nao serializa derruba
        o envio do LOTE inteiro, e nao so' daquele evento."""
        spawn = regras.montar_spawn("id1", "Fulano", 1, regras.limitar(regras.BARATO))
        json.dumps(spawn)

    def test_as_dancas_do_python_existem_no_config_do_roblox(self):
        """CONTRATO ENTRE OS DOIS LADOS. Uma danca que passe aqui e nao exista
        no Config.luau vira um boneco PARADO EM PE' no meio da formacao -- e o
        Roblox nao reclama de AnimationId inexistente."""
        config = os.path.join(RAIZ, "roblox", "src", "ReplicatedStorage",
                              "Config.luau")
        with open(config, encoding="utf-8") as f:
            texto = f.read()
        bloco = texto.split("DANCAS = {", 1)[1].split("}", 1)[0]
        for danca in regras.DANCAS_VALIDAS:
            self.assertIn(danca + " =", bloco,
                          f"a danca {danca!r} nao existe em Config.luau (DANCAS)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
