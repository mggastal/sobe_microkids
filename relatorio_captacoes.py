#!/usr/bin/env python3
"""
Relatório de Captações — Microkids (Sobé Estratégias)
Cruza a base de leads (xlsx exportado das LPs) com o investimento
Meta/Google do Google Sheets e gera captacoes.html (autocontido).

Uso: python3 relatorio_captacoes.py "<caminho do xlsx de leads>"
"""
import sys, json, re, io, subprocess, unicodedata, base64, hashlib
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path

LEADS_XLSX = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Downloads/[MICROKIDS] Leads Webnario.xlsx")
PNLD_XLSX  = str(Path.home() / "Downloads/Escolas_Exploradores_Digitais_PNLD_2027_matriculas (2).xlsx")
META_UF_XLS = str(Path.home() / "Downloads/CA---Microkids-Campanhas-7-de-set-de-2023-6-de-out-de-2026.xls")
SHEET_ID   = "1kKLTG5P6dPwYmXIRBm2DucM0bjk-rZJ0mzVNf3uyq5k"
OUT_HTML   = Path(__file__).with_name("captacoes.html")
TEMPLATE   = Path(__file__).with_name("captacoes_template.html")

def sheet_url(t): return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={t}"

def read_sheet(t):
    txt = subprocess.run(["curl", "-sfL", sheet_url(t)], capture_output=True, text=True, check=True).stdout
    return pd.read_csv(io.StringIO(txt))

def num(s):
    if pd.api.types.is_numeric_dtype(s): return s.fillna(0)
    return pd.to_numeric(s.astype(str).str.replace(",", ".", regex=False), errors="coerce").fillna(0)

# ══ CAPTAÇÕES ═══════════════════════════════════════════════════════
# key → nome, campanhas Meta / Google que compõem o investimento
CAPTS = [
    {"k": "w1",   "nome": "Webinar 01", "titulo": "Webinar 01 · Educação",
     "tema": "Webinário de Educação (julho)",
     "meta": ["SOBE-WEBNARIO01-CAPTACAO"],
     "google": ["SOBE-WEBNARIO01-CAPTACAO-PMAX", "SOBE-WEBNARIO01-CAPTACAO-DEMANDGEN-YOUTUBE", "SOBE-WEBNARIO01-CAPTACAO-SEARCH"]},
    {"k": "w2",   "nome": "Webinar 02", "titulo": "Webinar 02 · Educação",
     "tema": "Webinário de Educação (agosto)",
     "meta": ["SOBE-WEBNARIO02-CAPTACAO"], "google": []},
    {"k": "w3",   "nome": "Webinar 03", "titulo": "Webinar 03 · Conexões que Cuidam",
     "tema": "Webinário Conexões que Cuidam (setembro)",
     "meta": ["SOBE-WEBNARIO03-CAPTACAO"], "google": ["SOBE-WEBNARIO03-CAPTACAO-DEMANDGEN-YOUTUBE"]},
    {"k": "bncc", "nome": "Computação Desplugada", "titulo": "Computação Desplugada · BNCC",
     "tema": "Material BNCC — Computação Desplugada (set/out)",
     "meta": ["SOBE-BNCC"], "google": []},
]
# Captações de WhatsApp / e-book: leads ficam fora desta base → CPL pela conversão da plataforma
EXTRA_META = [
    {"nome": "PNLD 2027", "tipo": "WhatsApp / e-book", "camps": ["SOBE-PNLD2027-CAPTACAO"]},
    {"nome": "PNLD 2027 · Colab", "tipo": "WhatsApp / e-book", "camps": ["SOBE-PNLD2027-COLAB"]},
    {"nome": "Circuito", "tipo": "WhatsApp / e-book", "camps": ["SOBE-CIRCUITO"]},
    {"nome": "Robótica", "tipo": "WhatsApp / e-book", "camps": ["SOBE-ROBOTICA"]},
]

def capt_of(row):
    pg, d = row["pg"], row["Data"]
    if pg in ("webinar-educacao", "computacaodesplugada") and d < pd.Timestamp("2026-08-01"):
        return "w1"
    if pg in ("webinar-educacao", "computacaodesplugada") and d < pd.Timestamp("2026-09-01"):
        return "w2"
    if pg == "webinarmk-conexoesquecuidam": return "w3"
    if pg == "computacaodesplugada": return "bncc"
    return "outros"

# ══ CLASSIFICADORES ═════════════════════════════════════════════════
PLACEMENTS = {"Instagram_Feed", "Instagram_Stories", "Instagram_Reels", "Facebook_Mobile_Feed",
              "Facebook_Mobile_Reels", "Facebook_Stories", "Facebook_Desktop_Feed", "Threads_Feed",
              "Whatsapp_Status", "Facebook_Profile_Feed", "Instagram_Explore_Grid_Home",
              "Facebook_Instream_Video", "Others", "an"}
GOOGLE_CAMPS = {"pmax", "search", "youtube_demand_gen"}
EMPTY = {"undefined", "nan", "", "{{placement}}", "{{campaign.name}}", "{{adset.name}}", "{{ad.name}}"}

def fonte(r):
    s, m, c = r["utm_source"], r["utm_medium"], r["utm_campaign"]
    if s == "google_ads" or c in GOOGLE_CAMPS: return "Google Ads"
    if s == "RD Station" or m == "email": return "RD Station (e-mail)"
    if s in ("meta-ads", "ig") or s in PLACEMENTS or c.startswith("SOBE-") or c == "{{campaign.name}}" or s == "{{placement}}":
        return "Meta Ads"
    if s == "LPPNLD": return "LP PNLD (link)"
    if s in EMPTY: return "Direto / Não rastreado"
    return "Outros"

def placement(r):
    for v in (r["utm_content"], r["utm_source"]):
        if v in PLACEMENTS and v not in ("Others", "an"):
            return v.replace("_", " ")
    return None

ADSET_LBL = {
    "00-SEGUIDORES+ENG180+LEADS": "Públicos quentes",
    "01-INTERESSES-CARGOS": "Interesses (cargos)",
    "01-LAL1%-LEADS": "Lookalike 1% · Leads",
    "01-LAL1%-LEADSBET": "Lookalike 1% · Leads BET",
    "01-LAL1%-LEADS-SINEPE": "Lookalike 1% · SINEPE",
    "01-LAL1%-13CONG-PARTICIPANTES": "Lookalike 1% · 13º Congresso",
}
GOOGLE_LBL = {"pmax": "Performance Max", "youtube_demand_gen": "YouTube · Demand Gen", "search": "Search · Pesquisa"}
GOOGLE_CAMP_OF = {"pmax": "PMAX", "youtube_demand_gen": "DEMANDGEN-YOUTUBE", "search": "SEARCH"}

PROF_RULES = [
    ("Estudante / Em formação", r"estud|estagi|est[aá]gio|graduand|universit|aluno|acad[eê]mic|licenciand|doutorand|mestrand"),
    ("Saúde e Assistência Social", r"assistente social|servi[cç]o social|psic[oó]log|conselheir[oa] tutelar|enferm|terapeut|fonoaud|m[eé]dic|nutricion|cuidador"),
    ("Direção e Gestão", r"diret|dire[cç][aã]o|gestor|gest[aã]o|mantenedor|propriet|dono|\bs[oó]ci[oa]\b|ceo|fundador|founder|secret[aá]ri[oa] (de |municipal )?educa|presidente|empres[aá]ri|superintend|gerente"),
    ("Coordenação / Supervisão", r"coor?d|cood|supervis|chefe|articulador"),
    ("Pedagogia / Orientação", r"pedagog|pegagog|orienta|psicopedag"),
    ("Professor(a) / Educador(a)", r"prof|docente|educador|educadora|mestre|monitor|instrutor|regente|alfabetiz|tutor|\bpeb|teacher|maestr"),
    ("Especialista / Consultoria", r"consult|especialist|assessor|analist|formador|pesquisador|neuro|design"),
    ("Apoio / Administrativo", r"auxiliar|aux\.|assistente|administr|secret[aá]ri|apoio|mediador|agente|inspetor|bibliot|t[eé]cnic|atb|\bti\b"),
]
def prof_group(v):
    v = str(v).strip().lower()
    if v in ("", "nan", "-", ".") or len(v) < 2: return "Não informado"
    for lbl, rx in PROF_RULES:
        if re.search(rx, v): return lbl
    return "Outras áreas"

DDD_UF = {}
for uf, ddds in {
    "SP": "11 12 13 14 15 16 17 18 19", "RJ": "21 22 24", "ES": "27 28", "MG": "31 32 33 34 35 37 38",
    "PR": "41 42 43 44 45 46", "SC": "47 48 49", "RS": "51 53 54 55", "DF": "61", "GO": "62 64",
    "TO": "63", "MT": "65 66", "MS": "67", "AC": "68", "RO": "69", "BA": "71 73 74 75 77", "SE": "79",
    "PE": "81 87", "AL": "82", "PB": "83", "RN": "84", "CE": "85 88", "PI": "86 89", "PA": "91 93 94",
    "AM": "92 97", "RR": "95", "AP": "96", "MA": "98 99"}.items():
    for d in ddds.split(): DDD_UF[d] = uf
UF_NOME = {"SP": "São Paulo", "RJ": "Rio de Janeiro", "ES": "Espírito Santo", "MG": "Minas Gerais", "PR": "Paraná",
           "SC": "Santa Catarina", "RS": "Rio Grande do Sul", "DF": "Distrito Federal", "GO": "Goiás", "TO": "Tocantins",
           "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "AC": "Acre", "RO": "Rondônia", "BA": "Bahia", "SE": "Sergipe",
           "PE": "Pernambuco", "AL": "Alagoas", "PB": "Paraíba", "RN": "Rio Grande do Norte", "CE": "Ceará", "PI": "Piauí",
           "PA": "Pará", "AM": "Amazonas", "RR": "Roraima", "AP": "Amapá", "MA": "Maranhão"}
UF_REG = {**{u: "Sudeste" for u in "SP RJ ES MG".split()}, **{u: "Sul" for u in "PR SC RS".split()},
          **{u: "Centro-Oeste" for u in "DF GO MT MS".split()}, **{u: "Norte" for u in "TO AC RO PA AM RR AP".split()},
          **{u: "Nordeste" for u in "BA SE PE AL PB RN CE PI MA".split()}}

def ddd(tel):
    d = re.sub(r"\D", "", str(tel))
    if d.startswith("55") and len(d) >= 12: d = d[2:]
    d = d.lstrip("0")
    return d[:2] if len(d) >= 10 else None

# ══ CARGA ═══════════════════════════════════════════════════════════
def load_leads():
    df = pd.read_excel(LEADS_XLSX, sheet_name=0)
    for c in ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "pagina"]:
        df[c] = df[c].astype(str).str.strip()
    df["email"] = df["Email"].astype(str).str.strip().str.lower()
    teste = df["Nome"].astype(str).str.contains("teste", case=False) | df["email"].str.contains(
        r"@microkids\.com|@sobe\.|sandeepravi|teste@", regex=True)
    print(f"  Leads: {len(df)} linhas, {teste.sum()} testes/internos removidos")
    df = df[~teste].copy()
    df["pg"] = df["pagina"].str.rstrip("/").str.replace("lpmk.microkids.com/", "", regex=False)
    df["capt"] = df.apply(capt_of, axis=1)
    df["fonte"] = df.apply(fonte, axis=1)
    df["place"] = df.apply(placement, axis=1)
    df["prof"] = df["Cargo"].map(prof_group)
    df["ddd"] = df["Telefone"].map(ddd)
    df["uf"] = df["ddd"].map(DDD_UF)
    df["dia"] = df["Data"].dt.strftime("%Y-%m-%d")
    return df

def load_meta():
    m = read_sheet("meta-ads")
    m["sp"] = num(m["Spend (Cost, Amount Spent)"]); m["ld"] = num(m["Conversões"])
    m["imp"] = num(m["Impressions"]); m["lc"] = num(m["Action Link Clicks"]); m["pv"] = num(m["Action Landing Page View"])
    return m

def load_google():
    g = read_sheet("google-ads-outros")
    p = read_sheet("google-ads-pesquisa")
    g = pd.concat([g, p], ignore_index=True)
    g["sp"] = num(g["Cost (Spend, Amount Spent)"]); g["cv"] = num(g["All Conversions"])
    g["imp"] = num(g["Impressions"]); g["cl"] = num(g["Clicks"])
    return g

# ══ AGREGAÇÕES ══════════════════════════════════════════════════════
def bars(series, top=None):
    vc = series.dropna().value_counts()
    if top: vc = vc.head(top)
    return [{"label": k, "value": int(v)} for k, v in vc.items()]

def geo(d):
    u = d.dropna(subset=["uf"])
    est = []
    for uf, n in u["uf"].value_counts().items():
        ds = sorted(u.loc[u.uf == uf, "ddd"].unique())
        est.append({"label": UF_NOME[uf], "uf": uf, "reg": UF_REG[uf], "value": int(n), "ddds": ds})
    reg = u["uf"].map(UF_REG).value_counts()
    return {"com_uf": int(len(u)), "estados": est,
            "regioes": [{"label": k, "value": int(v)} for k, v in reg.items()]}

def utm_tab(d, col):
    rows = []
    for (v, f), n in d.groupby([col, "fonte"]).size().sort_values(ascending=False).items():
        if v in EMPTY: continue
        rows.append({"utm": v, "src": f, "value": int(n)})
    return rows

def daily(d, ini, fim):
    """Leads por semana (seg–dom), padrão em todo o relatório."""
    wk = d.groupby(d["Data"].dt.to_period("W-SUN")).size()
    per = pd.period_range(ini, fim, freq="W-SUN")
    return "semana", [{"date": p.start_time.strftime("%Y-%m-%d"), "value": int(wk.get(p, 0))} for p in per]

def spend_window(m, g, cfg):
    mm = m[m["Campaign Name"].isin(cfg["meta"])]
    gg = g[g["Campaign Name"].isin(cfg["google"])]
    return mm, gg

def build():
    leads = load_leads(); meta = load_meta(); goog = load_google()
    print(f"  Meta: {len(meta)} linhas | Google: {len(goog)} linhas")
    first_capt = leads.sort_values("Data").drop_duplicates("email").set_index("email")["capt"]

    out = {"capts": [], "geral": {}}
    resumo = []
    for cfg in CAPTS:
        d_all = leads[leads.capt == cfg["k"]]
        d = d_all.drop_duplicates("email")
        mm, gg = spend_window(meta, goog, cfg)
        sp_meta = float(mm["sp"].sum()); sp_g = float(gg["sp"].sum()); sp = sp_meta + sp_g
        ld_plat = float(mm["ld"].sum()) + float(gg["cv"].sum())
        ini = min([x for x in [d["Data"].min(), pd.to_datetime(mm["Date"]).min() if len(mm) else None] if x is not None and not pd.isna(x)])
        fim = max([x for x in [d["Data"].max(), pd.to_datetime(mm["Date"]).max() if len(mm) else None] if x is not None and not pd.isna(x)])
        ini, fim = ini.normalize(), fim.normalize()
        n = len(d)
        meta_d = d[d.fonte == "Meta Ads"]; goog_d = d[d.fonte == "Google Ads"]

        # conjuntos Meta: leads da base × investimento do conjunto
        conj = []
        sp_adset = mm.groupby("Adset Name").agg(sp=("sp", "sum"), ld=("ld", "sum"))
        lead_adset = meta_d["utm_medium"].value_counts()
        for a in sorted(set(sp_adset.index) | set(lead_adset.index), key=lambda a: -lead_adset.get(a, 0)):
            if a in EMPTY or (a not in sp_adset.index): continue
            s = float(sp_adset["sp"].get(a, 0)); l = int(lead_adset.get(a, 0))
            if s == 0 and l == 0: continue
            conj.append({"label": ADSET_LBL.get(a, a), "value": l, "spend": round(s, 2),
                         "plat": int(sp_adset["ld"].get(a, 0)), "cpl": round(s / l, 2) if l else None})

        google = []
        for c, l in goog_d["utm_campaign"].value_counts().items():
            suf = GOOGLE_CAMP_OF.get(c)
            s = float(gg.loc[gg["Campaign Name"].str.endswith(suf or "###"), "sp"].sum()) if suf else 0
            google.append({"label": GOOGLE_LBL.get(c, c), "value": int(l), "spend": round(s, 2),
                           "cpl": round(s / l, 2) if l and s else None})

        uni_novos = int((first_capt.reindex(d["email"]) == cfg["k"]).sum())
        gran, dd = daily(d_all, ini, fim)
        c = {
            "k": cfg["k"], "nome": cfg["nome"], "titulo": cfg["titulo"], "tema": cfg["tema"],
            "periodo": {"ini": ini.strftime("%Y-%m-%d"), "fim": fim.strftime("%Y-%m-%d")},
            "dias": int((fim - ini).days) + 1,
            "total": n, "cadastros": int(len(d_all)), "novos": uni_novos,
            "spend": round(sp, 2), "spend_meta": round(sp_meta, 2), "spend_google": round(sp_g, 2),
            "plat_leads": int(ld_plat), "cpl": round(sp / n, 2) if n else None,
            "cpl_plat": round(sp / ld_plat, 2) if ld_plat else None,
            "imp": int(mm["imp"].sum() + gg["imp"].sum()),
            "meta_total": int(len(meta_d)), "google_total": int(len(goog_d)),
            "diario_gran": gran, "diario": dd,
            "profissoes": bars(d["prof"]), "fontes": bars(d["fonte"]),
            "posicionamentos": bars(d["place"]),
            "conjuntos": conj, "google": google,
            "camp_tab": utm_tab(d, "utm_campaign"), "med_tab": utm_tab(d, "utm_medium"),
            "geo": geo(d),
            "base_incompleta": bool(ld_plat > 2.5 * max(n, 1)),
        }
        out["capts"].append(c)
        resumo.append(c)
        print(f"  {cfg['nome']:24s} leads {n:5d}  invest R$ {sp:9.2f}  CPL {c['cpl']}  plat {int(ld_plat)}")

    out["whats"] = build_whats(meta)
    extras = []
    for ex in EXTRA_META:
        mm = meta[meta["Campaign Name"].isin(ex["camps"])]
        if mm.empty: continue
        sp, pl = float(mm.sp.sum()), float(mm.ld.sum())
        extras.append({"nome": ex["nome"], "tipo": ex["tipo"], "camps": ex["camps"],
                       "spend": round(sp, 2), "plat": int(pl), "cpl": round(sp / pl, 2) if pl else None,
                       "imp": int(mm.imp.sum()), "ini": str(mm.Date.min()), "fim": str(mm.Date.max())})
        print(f"  {ex['nome']:24s} (fora da base) invest R$ {sp:9.2f}  leads plat {int(pl)}")

    # visão geral
    base = leads.drop_duplicates("email")
    capt_por_email = leads[leads.capt != "outros"].groupby("email")["capt"].nunique()
    mensal = leads.groupby([leads["Data"].dt.strftime("%Y-%m"), "capt"]).size().unstack(fill_value=0)
    sp_total = sum(c["spend"] for c in resumo)
    out["geral"] = {
        "cadastros": int(len(leads)), "unicos": int(len(base)),
        "spend": round(sp_total, 2),
        "spend_meta": round(sum(c["spend_meta"] for c in resumo), 2),
        "spend_google": round(sum(c["spend_google"] for c in resumo), 2),
        "periodo": {"ini": leads["Data"].min().strftime("%Y-%m-%d"), "fim": leads["Data"].max().strftime("%Y-%m-%d")},
        "outros": int((leads.capt == "outros").sum()),
        "recorrencia": [{"label": f"{k} captaç{'ão' if k == 1 else 'ões'}", "value": int(v)}
                        for k, v in capt_por_email.value_counts().sort_index().items()],
        "mensal": {"meses": list(mensal.index), "series": {k: [int(x) for x in mensal[k]] if k in mensal else [] for k in [c["k"] for c in CAPTS] + ["outros"]}},
        "profissoes": bars(base["prof"]), "fontes": bars(base["fonte"]), "geo": geo(base),
        "extras": extras,
        "gerado": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
    }
    web_ini = min(c["periodo"]["ini"] for c in resumo if c["k"] in ("w1", "w2", "w3"))
    web_fim = max(c["periodo"]["fim"] for c in resumo if c["k"] in ("w1", "w2", "w3"))
    out["pnld"] = build_pnld(leads, web_ini, web_fim)
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(out, ensure_ascii=False))
    here = Path(__file__).parent
    for ph, f in [("__LOGO_MK__", "logo.png"), ("__LOGO_SOBE__", "sobe_sm.png")]:
        html = html.replace(ph, "data:image/png;base64," + base64.b64encode((here / f).read_bytes()).decode())
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"  ✓ {OUT_HTML.name} gerado")

# ══ WHATSAPP / E-BOOK · detalhe por captação ═══════════════════════
def thumb_data(url):
    """Miniatura já baixada pelo dashboard.py (imgs/<md5>.ext), embutida em base64."""
    if not isinstance(url, str) or not url: return None
    ext = ".png" if ".png" in url.lower() else ".jpg"
    fp = Path(__file__).parent / "imgs" / (hashlib.md5(url.encode()).hexdigest()[:16] + ext)
    if not fp.exists(): return None
    try:  # reduz para 320px para o HTML não ficar pesado
        from PIL import Image
        im = Image.open(fp).convert("RGB"); im.thumbnail((320, 320))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=78)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return f"data:image/{'png' if ext == '.png' else 'jpeg'};base64," + base64.b64encode(fp.read_bytes()).decode()

def build_whats(meta):
    res = []
    for ex in EXTRA_META:
        mm = meta[meta["Campaign Name"].isin(ex["camps"])].copy()
        if mm.empty: continue
        mm["dt"] = pd.to_datetime(mm["Date"])
        sp, ld, imp, lc, pv = (float(mm[c].sum()) for c in ["sp", "ld", "imp", "lc", "pv"])
        ini, fim = mm["dt"].min(), mm["dt"].max()
        days = (fim - ini).days + 1
        per = mm["dt"].dt.to_period("W-SUN")  # sempre semanal (seg–dom), padrão do relatório
        g = mm.groupby(per)[["sp", "ld"]].sum()
        serie = [{"date": p_.start_time.strftime("%Y-%m-%d"), "leads": int(g["ld"].get(p_, 0)), "spend": round(float(g["sp"].get(p_, 0)), 2)}
                 for p_ in pd.period_range(ini, fim, freq="W-SUN")]
        gran = "semana"
        ads_g = mm.groupby(["Campaign Name", "Adset Name"])[["sp", "ld", "imp", "lc"]].sum().reset_index()
        publicos = [{"label": ADSET_LBL.get(r["Adset Name"], r["Adset Name"]), "camp": r["Campaign Name"].replace("SOBE-", ""),
                     "spend": round(float(r["sp"]), 2), "leads": int(r["ld"]), "imp": int(r["imp"]),
                     "cpl": round(float(r["sp"]) / r["ld"], 2) if r["ld"] else None}
                    for _, r in ads_g.sort_values("ld", ascending=False).iterrows() if r["sp"] > 0]
        an = mm.groupby(["Campaign Name", "Ad Name"]).agg(sp=("sp", "sum"), ld=("ld", "sum"), imp=("imp", "sum"), lc=("lc", "sum"),
                                                          thumb=("Thumbnail URL", "last"), ini=("dt", "min"), fim=("dt", "max")).reset_index()
        anuncios = [{"nome": r["Ad Name"], "camp": r["Campaign Name"].replace("SOBE-", ""), "spend": round(float(r["sp"]), 2),
                     "leads": int(r["ld"]), "imp": int(r["imp"]), "ctr": round(100 * r["lc"] / r["imp"], 2) if r["imp"] else None,
                     "cpl": round(float(r["sp"]) / r["ld"], 2) if r["ld"] else None, "img": thumb_data(r["thumb"]),
                     "ini": r["ini"].strftime("%Y-%m-%d"), "fim": r["fim"].strftime("%Y-%m-%d")}
                    for _, r in an.sort_values("sp", ascending=False).iterrows() if r["sp"] > 0]
        res.append({"k": re.sub(r"\W+", "", ex["nome"].lower()), "nome": ex["nome"], "tipo": ex["tipo"], "camps": ex["camps"],
                    "spend": round(sp, 2), "leads": int(ld), "cpl": round(sp / ld, 2) if ld else None,
                    "imp": int(imp), "cliques": int(lc), "lpv": int(pv), "ctr": round(100 * lc / imp, 2) if imp else None,
                    "cpm": round(1000 * sp / imp, 2) if imp else None, "conv_lpv": round(100 * ld / pv, 1) if pv else None,
                    "periodo": {"ini": ini.strftime("%Y-%m-%d"), "fim": fim.strftime("%Y-%m-%d")}, "dias": int(days),
                    "serie_gran": gran, "serie": serie, "publicos": publicos, "anuncios": anuncios})
        print(f"  WhatsApp/e-book {ex['nome']:20s} {len(anuncios)} anúncios, {len(publicos)} públicos")
    return res

# ══ PNLD 2027 · escolhas das escolas × investimento por estado ══════
META_REGIAO_UF = {"Acre (state)": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA", "Ceará": "CE",
    "Espírito Santo": "ES", "Federal District": "DF", "Goiás": "GO", "Maranhão": "MA", "Mato Grosso": "MT",
    "Mato Grosso do Sul": "MS", "Minas Gerais": "MG", "Paraná": "PR", "Paraíba": "PB", "Pará": "PA", "Pernambuco": "PE",
    "Piauí": "PI", "Rio Grande do Norte": "RN", "Rio Grande do Sul": "RS", "Rio de Janeiro (state)": "RJ",
    "Rondônia": "RO", "Roraima": "RR", "Santa Catarina": "SC", "Sergipe": "SE", "São Paulo (state)": "SP", "Tocantins": "TO"}

def read_xml_xls(path):
    """Export do Gerenciador de Anúncios (SpreadsheetML 2003)."""
    ns = "{urn:schemas-microsoft-com:office:spreadsheet}"
    rows = []
    for r in ET.parse(path).getroot().iter(ns + "Row"):
        vals = []
        for c in r.findall(ns + "Cell"):
            idx = c.get(ns + "Index")
            if idx:
                vals += [None] * (int(idx) - 1 - len(vals))
            d = c.find(ns + "Data"); vals.append(d.text if d is not None else None)
        rows.append(vals)
    return pd.DataFrame(rows[1:], columns=rows[0])

SCHOOL_STOP = set("""escola esc escolas municipal mun mul estadual est e m em emef emeif emei eef eeef ee eem eeem emeb cem
    colegio col de da do das dos ensino ens fundamental fun fund med medio infantil educacao basica unidade escolar ue ef
    eie centro integrado professor professora prof profa dr dra ii i iii iv n no na cei reunida indigena ind uef ueb eref
    liceu emee endereco ciep brizolao municipalizado nucleo vereador emeief emeef creche tia municipalizada""".split())
# nomes de patronos muito comuns: sozinhos não bastam para afirmar que é a mesma escola
SCHOOL_GENERIC = set("""sao santa santo sto nossa senhora aparecida francisco assis jose joao bom jesus vida nova boa vista
    duque caxias getulio vargas rui barbosa tancredo neves general osorio paulo freire arco iris maria lourdes bento
    cristovao andre terezinha perpetuo socorro conceicao pedro souza lagoa terra preta silva antonio alves oliveira
    araujo lima campos santos costa pereira ferreira rodrigues helena""".split())

def school_toks(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return set(t for t in re.sub(r"[^a-z0-9 ]", " ", s).split() if t not in SCHOOL_STOP and len(t) > 1)

def match_schools(leads, esc):
    """Escolas escolhidas cujo nome bate com o campo 'Escola' de um lead do mesmo estado (via DDD)."""
    esc = esc.assign(tok=esc["Escola"].map(school_toks))
    nomes = {c["k"]: c["nome"] for c in CAPTS}
    found = {}
    for _, l in leads.dropna(subset=["uf"]).iterrows():
        lt = school_toks(l["Escola"])
        if len(lt) < 2: continue
        for _, e in esc[esc["Estado"] == l["uf"]].iterrows():
            sh = lt & e["tok"]; dist = sh - SCHOOL_GENERIC
            same = lt == e["tok"] and len(sh) >= 3 and not {"nossa", "senhora"} <= sh
            if len(dist) >= 2 or (len(dist) >= 1 and len(sh) >= 3) or same:
                k = e["INEP"]
                f = found.setdefault(k, {"inep": str(k), "escola": e["Escola"].title(), "mun": e["Município"],
                                         "uf": e["Estado"], "pos": e["Posição da escolha"], "rede": e["Rede"].title(),
                                         "alunos": int(e["Total 3º ao 5º"]), "capts": [], "profs": []})
                cn = nomes.get(l["capt"], "Outras páginas")
                if cn not in f["capts"]: f["capts"].append(cn)
                if l["prof"] not in f["profs"]: f["profs"].append(l["prof"])
    return sorted(found.values(), key=lambda f: (f["pos"] != "Principal", f["uf"], f["escola"]))

def load_meta_regiao(ini, fim):
    """Investimento Meta de toda a conta por estado (aba breakdown-regiao) no período."""
    r = read_sheet("breakdown-regiao")
    r["sp"] = num(r["Spend (Cost, Amount Spent)"]); r["imp"] = num(r["Impressions"])
    r = r[(r["Date"] >= ini) & (r["Date"] <= fim)]
    r["uf"] = r["Region (Breakdown)"].map(META_REGIAO_UF)
    return r.groupby("uf")[["sp", "imp"]].sum(), float(r["sp"].sum())

def build_pnld(leads, web_ini, web_fim):
    esc = pd.read_excel(PNLD_XLSX, header=9).dropna(subset=["Estado"])
    esc = esc[esc["Estado"].isin(UF_NOME)]
    ca = read_xml_xls(META_UF_XLS)
    for c in ["Valor gasto (BRL)", "Impressões", "Alcance", "Cliques no link"]:
        ca[c] = pd.to_numeric(ca[c], errors="coerce").fillna(0)
    ca["uf"] = ca["Região"].map(META_REGIAO_UF)
    sp_uf = ca.groupby("uf")[["Valor gasto (BRL)", "Impressões", "Alcance", "Cliques no link"]].sum()
    sp_tot = float(ca["Valor gasto (BRL)"].sum())

    pos = esc.groupby(["Estado", "Posição da escolha"]).size().unstack(fill_value=0)
    mat = esc.groupby(["Estado", "Posição da escolha"])["Total 3º ao 5º"].sum().unstack(fill_value=0)
    mun = esc.groupby("Estado")["Município"].nunique()
    base_uf = leads.drop_duplicates("email")["uf"].value_counts()
    web = leads[leads["capt"].isin(["w1", "w2", "w3"])].drop_duplicates(["email", "capt"])
    web_uf = web["uf"].value_counts()
    web_capt = web.groupby(["uf", "capt"]).size()
    n_esc = len(esc)
    all_uf, all_tot = load_meta_regiao(web_ini, web_fim)
    ufs = []
    for uf in UF_NOME:
        pr, sg = int(pos.loc[uf].get("Principal", 0)) if uf in pos.index else 0, int(pos.loc[uf].get("Segunda opção", 0)) if uf in pos.index else 0
        sp = float(sp_uf["Valor gasto (BRL)"].get(uf, 0))
        tot = pr + sg
        ufs.append({"uf": uf, "nome": UF_NOME[uf], "reg": UF_REG[uf], "principal": pr, "segunda": sg, "escolas": tot,
                    "alunos": int(mat.loc[uf].sum()) if uf in mat.index else 0,
                    "alunos_principal": int(mat.loc[uf].get("Principal", 0)) if uf in mat.index else 0,
                    "municipios": int(mun.get(uf, 0)), "spend": round(sp, 2),
                    "imp": int(sp_uf["Impressões"].get(uf, 0)), "alcance": int(sp_uf["Alcance"].get(uf, 0)),
                    "cliques": int(sp_uf["Cliques no link"].get(uf, 0)), "leads_base": int(base_uf.get(uf, 0)),
                    "leads_web": int(web_uf.get(uf, 0)),
                    "leads_w": {k: int(web_capt.get((uf, k), 0)) for k in ["w1", "w2", "w3"]},
                    "sh_spend": round(100 * sp / sp_tot, 2), "sh_escolas": round(100 * tot / n_esc, 2),
                    "spend_all": round(float(all_uf["sp"].get(uf, 0)), 2),
                    "sh_spend_all": round(100 * float(all_uf["sp"].get(uf, 0)) / all_tot, 2),
                    "custo_escola": round(sp / tot, 2) if tot else None})
    t = pd.DataFrame(ufs)
    spear = lambda a, b: round(float(t[a].rank().corr(t[b].rank())), 2)
    camps = ca.groupby("Nome da campanha")[["Valor gasto (BRL)", "Impressões", "Alcance", "Cliques no link"]].sum()
    matches = match_schools(leads, esc)
    print(f"  PNLD: {n_esc} escolas, {t.uf[t.escolas > 0].nunique()} UFs, invest R$ {sp_tot:.2f}, "
          f"Spearman {spear('spend', 'escolas')}, {len(matches)} escolas com lead na base")
    def top_mun(posicao, n=12):
        d = esc[esc["Posição da escolha"] == posicao]
        g = d.groupby(["Município", "Estado"]).agg(escolas=("INEP", "count"), alunos=("Total 3º ao 5º", "sum"))
        g = g.sort_values(["escolas", "alunos"], ascending=False).head(n).reset_index()
        return [{"mun": r["Município"], "uf": r["Estado"], "escolas": int(r["escolas"]), "alunos": int(r["alunos"])}
                for _, r in g.iterrows()]
    return {
        "escolas": n_esc, "principal": int((esc["Posição da escolha"] == "Principal").sum()),
        "segunda": int((esc["Posição da escolha"] == "Segunda opção").sum()),
        "alunos": int(esc["Total 3º ao 5º"].sum()),
        "alunos_principal": int(esc.loc[esc["Posição da escolha"] == "Principal", "Total 3º ao 5º"].sum()),
        "ufs": int(esc["Estado"].nunique()), "municipios": int(esc.groupby(["Estado", "Município"]).ngroups),
        "rede": {k: int(v) for k, v in esc["Rede"].value_counts().items()},
        "spend_all": round(all_tot, 2), "periodo_all": {"ini": web_ini, "fim": web_fim},
        "spend_all_sem_uf": round(all_tot - float(all_uf["sp"].sum()), 2),
        "spend": round(sp_tot, 2), "spend_sem_uf": round(float(ca.loc[ca.uf.isna(), "Valor gasto (BRL)"].sum()), 2),
        "imp": int(ca["Impressões"].sum()), "alcance_uf": int(ca["Alcance"].sum()), "cliques": int(ca["Cliques no link"].sum()),
        "campanhas": [{"nome": k, "spend": round(float(v["Valor gasto (BRL)"]), 2), "imp": int(v["Impressões"])} for k, v in camps.iterrows()],
        "periodo": {"ini": str(ca["Início dos relatórios"].min()), "fim": str(ca["Encerramento dos relatórios"].max())},
        "corr": {"escolas": spear("spend", "escolas"), "principal": spear("spend", "principal"), "alunos": spear("spend", "alunos"),
                 "web_escolas": spear("leads_web", "escolas"), "web_principal": spear("leads_web", "principal")},
        "map": json.loads((Path(__file__).parent / "brazil_map.json").read_text()),
        "ufs_list": ufs, "matches": matches,
        "top_mun_1": top_mun("Principal"), "top_mun_2": top_mun("Segunda opção"),
    }

if __name__ == "__main__":
    build()
