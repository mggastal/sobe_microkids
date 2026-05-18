#!/usr/bin/env python3
"""
Gerador Dashboard Lançamento Gratuito v2 — ALL CONVERSIONS
==========================================================
DIFERENÇA vs v1: leads = soma de 4 colunas de conversão:
  - Action FB Pixel Custom (Offsite Conversion)
  - Action Messaging Conversations Started (Onsite Conversion)
  - Action Leads
  - Conversion Contact Total

ATENÇÃO: este gerador deve ser usado JUNTO com o template
  dashboard_lancamento_gratuito_v2_all_conv.html
"""

import pandas as pd, json, re, hashlib, requests
from datetime import date
from pathlib import Path

# ══════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════

SHEET_ID         = "1kKLTG5P6dPwYmXIRBm2DucM0bjk-rZJ0mzVNf3uyq5k"
TEMPLATE_FILE    = "dashboard.html"
OUTPUT_FILE      = "index.html"

NOME_CLIENTE     = "Microkids"
LOGO_LETRA       = "MK"
COR_ACENTO       = "#AD96DC"

LANCAMENTO_COD   = ""        # filtra campanhas; "" = ver tudo
USAR_PESQUISA    = False            # False = oculta aba Pesquisa

# Metas do funil — define cores (verde/amarelo/vermelho)
CPL_BOM          = 40.0    # Custo por Lead ≤ 5 → verde | 5-10 → amarelo | acima → vermelho
CPL_MEDIO        = 45.0
CTR_BOM          = 0.6    # CTR ≥ 1.2% → verde | 0.8-1.2% → amarelo | abaixo → vermelho
CTR_MEDIO        = 0.4
CR_BOM           = 68.0   # Connect Rate ≥ 40% → verde | 25-40% → amarelo | abaixo → vermelho
CR_MEDIO         = 60.0
TX_CONV_BOM      = 3.0   # Taxa Conversão (Lead/PV) ≥ 30% → verde | 15-30% → amarelo | abaixo → vermelho
TX_CONV_MEDIO    = 2.0
CPM_BOM          = 5.0    # CPM ≤ 5 → verde | 5-12 → amarelo | acima → vermelho (menor = melhor)
CPM_MEDIO        = 12.0

# ══════════════════════════════════════════════════════
def sheet_url(t): return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={t}"
URL_META = sheet_url("meta-ads")
URL_PES  = sheet_url("Pesquisa")
URL_GA   = sheet_url("breakdown-gender-age")
URL_PT   = sheet_url("breakdown-platform")

def to_num(s):
    if pd.api.types.is_numeric_dtype(s): return s.fillna(0)
    clean = s.astype(str).str.strip().str.replace("R$","",regex=False).str.strip()
    if clean.str.contains(r"\d,\d", regex=True).any():
        clean = clean.str.replace(".","",regex=False).str.replace(",",".",regex=False)
    return pd.to_numeric(clean, errors="coerce").fillna(0)

def safe(v):
    if v is None or (isinstance(v,float) and pd.isna(v)): return None
    return round(float(v),2) if float(v)!=0 else None

def download_thumb(url, d):
    if not url or str(url)=="nan": return ""
    try:
        ext=".png" if ".png" in url.lower() else ".jpg"
        fname=hashlib.md5(url.encode()).hexdigest()[:16]+ext
        fp=d/fname
        if not fp.exists():
            r=requests.get(url,timeout=10,headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code==200: fp.write_bytes(r.content)
            else: return ""
        return "imgs/"+fname
    except: return ""

# ══ META ADS ══════════════════════════════════════════
# Colunas de conversão somadas para "leads" nesta versão v2
CONV_COLS = [
    "Action FB Pixel Custom (Offsite Conversion)",
    "Action Messaging Conversations Started (Onsite Conversion)",
    "Action Leads",
    "Conversion Contact Total",
]

def load_meta():
    print("  Lendo meta-ads...")
    df=pd.read_csv(URL_META)
    df=df.rename(columns={
        "Date":"date","Campaign Name":"campaign","Adset Name":"adset",
        "Ad Name":"ad","Thumbnail URL":"thumb",
        "Spend (Cost, Amount Spent)":"spend",
        "Impressions":"impressions",
        "Action Link Clicks":"link_clicks",
        "Action Landing Page View":"page_view",
    })
    df["date"]=pd.to_datetime(df["date"],errors="coerce")
    for c in ["spend","impressions","link_clicks","page_view"]:
        if c in df.columns: df[c]=to_num(df[c])
    # Somar todas as colunas de conversão disponíveis
    df["leads"] = sum(to_num(df[c]) for c in CONV_COLS if c in df.columns)
    print(f"     Conversões somadas: {', '.join(c for c in CONV_COLS if c in df.columns)}")
    df["is_lct"]=df["campaign"].str.contains(LANCAMENTO_COD,na=False,case=False) if LANCAMENTO_COD else True
    df=df.dropna(subset=["date"])
    print(f"     {len(df)} linhas | {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"     Total conversões: {df['leads'].sum():.0f}")
    return df

def calc_kpis(p):
    sp=float(p["spend"].sum()); imp=float(p["impressions"].sum())
    lc=float(p["link_clicks"].sum()); pv=float(p["page_view"].sum())
    ld=float(p["leads"].sum())
    return {
        "spend":round(sp,2),"impressions":int(imp),"link_clicks":int(lc),
        "page_view":int(pv),"leads":int(ld),
        "ctr":   round(lc/imp*100,2) if imp>0 else None,
        "connect_rate":round(pv/lc*100,2) if lc>0 else None,
        "tx_conv":round(ld/pv*100,2) if pv>0 else None,
        "cpl":   round(sp/ld,2) if ld>0 else None,
        "cpm":   round(sp/imp*1000,2) if imp>0 else None
    }

def meta_kpis(df):
    return {"lct":calc_kpis(df[df["is_lct"]]),"all":calc_kpis(df)}

def build_daily(p):
    # Coluna de engajamento — usa Action Post Engagement se disponível
    ENG_COL = "Action Post Engagement"
    has_eng = ENG_COL in p.columns
    agg_cols = dict(spend=("spend","sum"),impressions=("impressions","sum"),
        link_clicks=("link_clicks","sum"),page_view=("page_view","sum"),leads=("leads","sum"))
    if has_eng: agg_cols["engagement"] = (ENG_COL,"sum")
    agg=p.groupby("date").agg(**agg_cols).reset_index().sort_values("date")
    out={k:[] for k in ["days","spend","impressions","link_clicks","page_view","leads",
                         "ctr","connect_rate","tx_conv","cpl","cpm","engagement","cpe"]}
    for _,r in agg.iterrows():
        sp=float(r["spend"]); imp=float(r["impressions"]); lc=float(r["link_clicks"])
        pv=float(r["page_view"]); ld=float(r["leads"])
        eng=float(r["engagement"]) if has_eng else 0
        out["days"].append(r["date"].strftime("%d/%m"))
        out["spend"].append(round(sp,2)); out["impressions"].append(int(imp))
        out["link_clicks"].append(int(lc)); out["page_view"].append(int(pv))
        out["leads"].append(int(ld)); out["engagement"].append(int(eng))
        out["ctr"].append(round(lc/imp*100,2) if imp>0 else None)
        out["connect_rate"].append(round(pv/lc*100,2) if lc>0 else None)
        out["tx_conv"].append(round(ld/pv*100,2) if pv>0 else None)
        out["cpl"].append(round(sp/ld,2) if ld>0 else None)
        out["cpm"].append(round(sp/imp*1000,2) if imp>0 else None)
        out["cpe"].append(round(sp/eng,2) if eng>0 else None)
    return out

def meta_daily(df):
    return {"lct":build_daily(df[df["is_lct"]]),"all":build_daily(df)}

def meta_daily_camps(df):
    result={"lct":{},"all":{}}
    for key,subset in [("lct",df[df["is_lct"]]),("all",df)]:
        for camp in subset["campaign"].unique():
            result[key][camp]=build_daily(subset[subset["campaign"]==camp])
    return result

def meta_raw(df):
    rows=[]
    agg=df.groupby(["date","campaign","adset","is_lct"]).agg(
        spend=("spend","sum"),leads=("leads","sum"),
        impressions=("impressions","sum"),link_clicks=("link_clicks","sum"),
        page_view=("page_view","sum")
    ).reset_index()
    for _,r in agg.iterrows():
        rows.append({
            "d":r["date"].strftime("%d/%m"),"c":str(r["campaign"]),"a":str(r["adset"]),
            "lct":bool(r["is_lct"]),"sp":round(float(r["spend"]),2),
            "ld":int(r["leads"]),"imp":int(r["impressions"]),
            "lc":int(r["link_clicks"]),"pv":int(r["page_view"])
        })
    return rows

def meta_tables_period(df, p, img_dir):
    def ag(sub,cols): return sub.groupby(cols).agg(spend=("spend","sum"),impressions=("impressions","sum"),link_clicks=("link_clicks","sum"),page_view=("page_view","sum"),leads=("leads","sum")).reset_index()

    def calc_row(r):
        sp=round(float(r["spend"]),2); imp=int(r["impressions"]); lc=int(r["link_clicks"])
        pv=int(r["page_view"]); ld=int(r["leads"])
        return {"spend":sp,"imp":imp,"lc":lc,"pv":pv,"ld":ld,
            "ctr":round(lc/imp*100,2) if imp>0 else None,
            "cr":round(pv/lc*100,2) if lc>0 else None,
            "tx_cv":round(ld/pv*100,2) if pv>0 else None,
            "cpl":round(sp/ld,2) if ld>0 else None,
            "cpm":round(sp/imp*1000,2) if imp>0 else None}

    camps_agg=ag(p,"campaign")
    camps=[{"n":str(r["campaign"]),**calc_row(r)} for _,r in camps_agg.sort_values("leads",ascending=False).iterrows()]

    adsets_agg=ag(p,["campaign","adset"])
    adsets=[{"n":str(r["adset"]),"camp":str(r["campaign"]),**calc_row(r)} for _,r in adsets_agg.sort_values("leads",ascending=False).iterrows()]

    # Thumbs do df completo
    df_full_thumb=df[df["thumb"].notna()&(df["thumb"].astype(str)!="nan")] if "thumb" in df.columns else pd.DataFrame()
    thumb_map={}
    for _,r in df_full_thumb.iterrows():
        k=(str(r["ad"]),str(r["adset"]),str(r["campaign"]))
        if k not in thumb_map: thumb_map[k]=download_thumb(str(r["thumb"]),img_dir)

    ads_agg=p.groupby(["ad","adset","campaign"]).agg(spend=("spend","sum"),impressions=("impressions","sum"),link_clicks=("link_clicks","sum"),leads=("leads","sum")).reset_index().sort_values("leads",ascending=False)
    ads=[]
    for _,r in ads_agg.iterrows():
        sp=round(float(r["spend"]),2); imp=int(r["impressions"]); lc=int(r["link_clicks"]); ld=int(r["leads"])
        k=(str(r["ad"]),str(r["adset"]),str(r["campaign"]))
        ads.append({"n":str(r["ad"]),"adset":str(r["adset"]),"camp":str(r["campaign"]),
            "thumb":thumb_map.get(k,""),"spend":sp,"imp":imp,"lc":lc,"ld":ld,
            "ctr":round(lc/imp*100,2) if imp>0 else None,
            "cpl":round(sp/ld,2) if ld>0 else None})
    return {"camps":camps,"adsets":adsets,"ads":ads}

def meta_tables(df, img_dir):
    hoje=pd.Timestamp(date.today())
    ontem=hoje-pd.Timedelta(days=1)
    result={"lct":{},"all":{}}
    period_ranges={
        "1":  (ontem, ontem),
        "7":  (hoje-pd.Timedelta(days=6), hoje),
        "14": (hoje-pd.Timedelta(days=13), hoje),
        "30": (hoje-pd.Timedelta(days=29), hoje),
        "all": (None, None),
    }
    for key,subset in [("lct",df[df["is_lct"]]),("all",df)]:
        for pname,(start,end) in period_ranges.items():
            if start is None:
                p=subset
            else:
                p=subset[(subset["date"]>=start)&(subset["date"]<=end)]
            result[key][pname]=meta_tables_period(df,p,img_dir)
            print(f"     [{key}][{pname}]: {len(result[key][pname]['camps'])} camps | {len(result[key][pname]['ads'])} ads")
    return result

def meta_breakdowns(df):
    print("  Lendo breakdowns...")
    hoje_bd=pd.Timestamp(date.today())
    AGE_ORDER=["18-24","25-34","35-44","45-54","55-64","65+"]
    # Soma de todas as colunas de conversão disponíveis no breakdown
    # Adicione Action FB Pixel Custom (Offsite Conversion) nas abas do Sheets para incluir
    CONV_COLS_BD = [
        "Action FB Pixel Custom (Offsite Conversion)",
        "Action Messaging Conversations Started (Onsite Conversion)",
        "Action Leads",
        "Conversion Contact Total",
    ]
    def seg(agg, dim):
        agg=agg[agg["spend"]>0].copy()
        agg["cpl"]=(agg["spend"]/agg["leads"]).where(agg["leads"]>0).round(2)
        return [{"n":str(r[dim]),"spend":round(float(r["spend"]),2),"ld":int(r["leads"]),"cpl":safe(r["cpl"])} for _,r in agg.iterrows()]
    try:
        df_ga=pd.read_csv(URL_GA)
        df_ga["date"]=pd.to_datetime(df_ga["Date"],errors="coerce")
        df_ga["spend"]=to_num(df_ga["Spend (Cost, Amount Spent)"])
        # Soma das colunas disponíveis — inclui FB Pixel Custom se existir na aba
        available=[c for c in CONV_COLS_BD if c in df_ga.columns]
        print(f"     GA colunas de conv: {available}")
        df_ga["leads"]=sum(to_num(df_ga[c]) for c in available) if available else pd.Series(0, index=df_ga.index)
        df_ga["age"]=df_ga["Age (Breakdown)"].astype(str)
        df_ga["gender"]=df_ga["Gender (Breakdown)"].astype(str)
        if "Campaign Name" in df_ga.columns and LANCAMENTO_COD:
            df_ga["is_lct"]=df_ga["Campaign Name"].str.contains(LANCAMENTO_COD,na=False,case=False)
        else:
            df_ga["is_lct"]=True
        df_ga=df_ga.dropna(subset=["date"])
    except Exception as e: print(f"  Aviso GA: {e}"); df_ga=pd.DataFrame()
    try:
        df_pt=pd.read_csv(URL_PT)
        df_pt["date"]=pd.to_datetime(df_pt["Date"],errors="coerce")
        df_pt["spend"]=to_num(df_pt["Spend (Cost, Amount Spent)"])
        # Soma das colunas disponíveis — inclui FB Pixel Custom se existir na aba
        available_pt=[c for c in CONV_COLS_BD if c in df_pt.columns]
        print(f"     PT colunas de conv: {available_pt}")
        df_pt["leads"]=sum(to_num(df_pt[c]) for c in available_pt) if available_pt else pd.Series(0, index=df_pt.index)
        df_pt["platform"]=df_pt["Platform Position (Breakdown)"].astype(str)
        if "Campaign Name" in df_pt.columns and LANCAMENTO_COD:
            df_pt["is_lct"]=df_pt["Campaign Name"].str.contains(LANCAMENTO_COD,na=False,case=False)
        else:
            df_pt["is_lct"]=True
        df_pt=df_pt.dropna(subset=["date"])
    except Exception as e: print(f"  Aviso PT: {e}"); df_pt=pd.DataFrame()

    result={}
    for pname,n in [("1",1),("7",7),("14",14),("30",30),("all",0)]:
        start=hoje_bd-pd.Timedelta(days=n-1) if n>0 else None
        for lname,lct_filter in [("lct",True),("all",None)]:
            if len(df_ga)>0:
                pga=df_ga if lct_filter is None else df_ga[df_ga["is_lct"]]
                pga=pga[(pga["date"]>=start)&(pga["date"]<=hoje_bd)] if n>0 else pga
            else: pga=df_ga
            if len(df_pt)>0:
                ppt=df_pt if lct_filter is None else df_pt[df_pt["is_lct"]]
                ppt=ppt[(ppt["date"]>=start)&(ppt["date"]<=hoje_bd)] if n>0 else ppt
            else: ppt=df_pt
            age_d=[]; gen_d=[]; plat_d=[]
            if len(pga)>0:
                ag_age=pga[pga["age"].isin(AGE_ORDER)].groupby("age").agg(spend=("spend","sum"),leads=("leads","sum")).reset_index()
                ag_age["_o"]=ag_age["age"].apply(lambda x:AGE_ORDER.index(x) if x in AGE_ORDER else 99)
                age_d=seg(ag_age.sort_values("_o"),"age")
                ag_gen=pga[pga["gender"].isin(["female","male"])].groupby("gender").agg(spend=("spend","sum"),leads=("leads","sum")).reset_index().sort_values("leads",ascending=False)
                gen_d=seg(ag_gen,"gender")
            if len(ppt)>0:
                ag_pt=ppt.groupby("platform").agg(spend=("spend","sum"),leads=("leads","sum")).reset_index().sort_values("leads",ascending=False).head(8)
                plat_d=seg(ag_pt,"platform")
            if lname not in result: result[lname]={}
            result[lname][pname]={"age":age_d,"gender":gen_d,"platform":plat_d}

    raw_ga=[]
    if len(df_ga)>0:
        for _,r in df_ga.iterrows():
            if pd.isna(r['date']): continue
            raw_ga.append({'d':r['date'].strftime('%d/%m'),'age':str(r['age']),'gen':str(r['gender']),
                           'sp':round(float(r['spend']),2),'ld':int(r['leads']),
                           'lct':bool(r['is_lct']),'camp':str(r['Campaign Name']) if 'Campaign Name' in r.index else ''})
    raw_pt=[]
    if len(df_pt)>0:
        for _,r in df_pt.iterrows():
            if pd.isna(r['date']): continue
            raw_pt.append({'d':r['date'].strftime('%d/%m'),'plat':str(r['platform']),
                           'sp':round(float(r['spend']),2),'ld':int(r['leads']),
                           'lct':bool(r['is_lct']),'camp':str(r['Campaign Name']) if 'Campaign Name' in r.index else ''})
    result['_raw_ga']=raw_ga; result['_raw_pt']=raw_pt
    return result

# ══ GOOGLE ADS ════════════════════════════════════════
URL_GOOGLE   = sheet_url("google-ads")
URL_GOOGLE_GE= sheet_url("google-breakdown-gender")
URL_GOOGLE_AG= sheet_url("google-breakdown-age")

AGE_MAP = {"AGE_RANGE_18_24":"18-24","AGE_RANGE_25_34":"25-34","AGE_RANGE_35_44":"35-44",
           "AGE_RANGE_45_54":"45-54","AGE_RANGE_55_64":"55-64","AGE_RANGE_65_UP":"65+"}

def load_google():
    print("  Lendo google-ads...")
    df=pd.read_csv(URL_GOOGLE)
    df["date"]=pd.to_datetime(df["Date (Segment)"],errors="coerce")
    df["spend"]=to_num(df["Cost (Spend, Amount Spent)"])
    df["conversions"]=to_num(df["All Conversions"])
    df["clicks"]=to_num(df["Clicks"])
    df["impressions"]=to_num(df["Impressions"])
    df["campaign"]=df["Campaign Name"]
    df["adgroup"]=df["Ad Group Name"]
    df["keyword"]=df["Keyword (Ad Group Criterion)"]
    df["match_type"]=df["Match Type (Segment)"]
    df=df.dropna(subset=["date"])
    print(f"     {len(df)} linhas | {df['date'].min().date()} → {df['date'].max().date()}")
    return df

def google_daily(df):
    agg=df.groupby("date").agg(spend=("spend","sum"),conversions=("conversions","sum"),
        clicks=("clicks","sum"),impressions=("impressions","sum")).reset_index().sort_values("date")
    out={k:[] for k in ["days","spend","conversions","cpa","ctr","cpc"]}
    for _,r in agg.iterrows():
        sp=round(float(r["spend"]),2); cv=round(float(r["conversions"]),2)
        cl=int(r["clicks"]); imp=int(r["impressions"])
        out["days"].append(r["date"].strftime("%d/%m"))
        out["spend"].append(sp); out["conversions"].append(cv)
        out["cpa"].append(round(sp/cv,2) if cv>0 else None)
        out["ctr"].append(round(cl/imp*100,2) if imp>0 else None)
        out["cpc"].append(round(sp/cl,2) if cl>0 else None)
    return out

def google_kpis(df):
    hoje=pd.Timestamp(date.today()); ontem=hoje-pd.Timedelta(days=1)
    def kpi(p):
        sp=float(p["spend"].sum()); cv=float(p["conversions"].sum())
        cl=int(p["clicks"].sum()); imp=int(p["impressions"].sum())
        return {"spend":round(sp,2),"conversions":round(cv,2),"clicks":cl,"impressions":imp,
                "cpa":round(sp/cv,2) if cv>0 else None,
                "ctr":round(cl/imp*100,2) if imp>0 else None,
                "cpc":round(sp/cl,2) if cl>0 else None}
    result={}
    result["1"]=kpi(df[(df["date"]>=ontem)&(df["date"]<=ontem)])
    for n in [7,14,30]: result[str(n)]=kpi(df[df["date"]>=hoje-pd.Timedelta(days=n-1)])
    result["all"]=kpi(df)
    return result

def google_camps(df):
    hoje=pd.Timestamp(date.today()); ontem=hoje-pd.Timedelta(days=1)
    def camps_period(p):
        if not len(p): return []
        ag=p.groupby("campaign").agg(spend=("spend","sum"),conversions=("conversions","sum"),
            clicks=("clicks","sum"),impressions=("impressions","sum")).reset_index()
        rows=[]
        for _,r in ag.sort_values("conversions",ascending=False).iterrows():
            sp=round(float(r["spend"]),2); cv=round(float(r["conversions"]),2)
            cl=int(r["clicks"]); imp=int(r["impressions"])
            # Grupos de anúncio
            adg=p[p["campaign"]==r["campaign"]].groupby("adgroup").agg(spend=("spend","sum"),conversions=("conversions","sum"),
                clicks=("clicks","sum"),impressions=("impressions","sum")).reset_index()
            adgroups=[]
            for _,ag2 in adg.sort_values("conversions",ascending=False).iterrows():
                sp2=round(float(ag2["spend"]),2); cv2=round(float(ag2["conversions"]),2)
                cl2=int(ag2["clicks"]); imp2=int(ag2["impressions"])
                # keywords — incluir match, impressions e ctr
                kws=p[(p["campaign"]==r["campaign"])&(p["adgroup"]==ag2["adgroup"])].groupby("keyword").agg(
                    spend=("spend","sum"),conversions=("conversions","sum"),
                    clicks=("clicks","sum"),impressions=("impressions","sum")).reset_index()
                kw_list=[]
                for _,k in kws.sort_values("conversions",ascending=False).iterrows():
                    sp_k=round(float(k["spend"]),2); cv_k=round(float(k["conversions"]),2)
                    cl_k=int(k["clicks"]); imp_k=int(k["impressions"])
                    mt=p[(p["campaign"]==r["campaign"])&(p["adgroup"]==ag2["adgroup"])&(p["keyword"]==k["keyword"])]["match_type"]
                    kw_list.append({"n":str(k["keyword"]),
                        "match":str(mt.mode()[0]) if len(mt)>0 else "",
                        "spend":sp_k,"conv":cv_k,
                        "cpa":round(sp_k/cv_k,2) if cv_k>0 else None,
                        "cpc":round(sp_k/cl_k,2) if cl_k>0 else None,
                        "ctr":round(cl_k/imp_k*100,2) if imp_k>0 else None,
                        "clicks":cl_k,"imp":imp_k})
                adgroups.append({"n":str(ag2["adgroup"]),"spend":sp2,"conv":cv2,
                    "cpa":round(sp2/cv2,2) if cv2>0 else None,"cpc":round(sp2/cl2,2) if cl2>0 else None,
                    "ctr":round(cl2/imp2*100,2) if imp2>0 else None,"clicks":cl2,"imp":imp2,"keywords":kw_list})
            rows.append({"n":str(r["campaign"]),"spend":sp,"conv":cv,
                "cpa":round(sp/cv,2) if cv>0 else None,"cpc":round(sp/cl,2) if cl>0 else None,
                "ctr":round(cl/imp*100,2) if imp>0 else None,"clicks":cl,"imp":imp,"adgroups":adgroups})
        return rows
    result={}
    result["1"]=camps_period(df[(df["date"]>=ontem)&(df["date"]<=ontem)])
    for n in [7,14,30]: result[str(n)]=camps_period(df[df["date"]>=hoje-pd.Timedelta(days=n-1)])
    result["all"]=camps_period(df)
    return result

def google_keywords(df):
    hoje=pd.Timestamp(date.today()); ontem=hoje-pd.Timedelta(days=1)
    def kws_period(p):
        ag=p.groupby("keyword").agg(spend=("spend","sum"),conversions=("conversions","sum"),
            clicks=("clicks","sum"),impressions=("impressions","sum")).reset_index()
        ag=ag[ag["spend"]>0].sort_values("conversions",ascending=False).head(25)
        rows=[]
        for _,k in ag.iterrows():
            sp=round(float(k["spend"]),2); cv=round(float(k["conversions"]),2)
            cl=int(k["clicks"]); imp=int(k["impressions"])
            mt=p[p["keyword"]==k["keyword"]]["match_type"]
            rows.append({"n":str(k["keyword"]),"match":str(mt.mode()[0]) if len(mt)>0 else "",
                "spend":sp,"conv":cv,
                "cpa":round(sp/cv,2) if cv>0 else None,
                "cpc":round(sp/cl,2) if cl>0 else None,
                "ctr":round(cl/imp*100,2) if imp>0 else None,
                "clicks":cl,"imp":imp})
        return rows
    result={}
    result["1"]=kws_period(df[(df["date"]>=ontem)&(df["date"]<=ontem)])
    for n in [7,14,30]: result[str(n)]=kws_period(df[df["date"]>=hoje-pd.Timedelta(days=n-1)])
    result["all"]=kws_period(df)
    return result

def google_raw(df):
    """Raw diário por campanha/adgroup/keyword — usado para filtros de data livre no HTML."""
    rows=[]
    agg=df.groupby(["date","campaign","adgroup","keyword","match_type"]).agg(
        spend=("spend","sum"),conversions=("conversions","sum"),
        clicks=("clicks","sum"),impressions=("impressions","sum")
    ).reset_index()
    for _,r in agg.iterrows():
        rows.append({
            "d": r["date"].strftime("%d/%m"),
            "c": str(r["campaign"]), "a": str(r["adgroup"]),
            "kw": str(r["keyword"]), "mt": str(r["match_type"]),
            "sp": round(float(r["spend"]),2),
            "cv": round(float(r["conversions"]),2),
            "cl": int(r["clicks"]), "imp": int(r["impressions"])
        })
    return rows

def google_breakdowns(df):
    print("  Lendo breakdowns Google...")
    hoje=pd.Timestamp(date.today()); ontem=hoje-pd.Timedelta(days=1)
    try:
        df_a=pd.read_csv(URL_GOOGLE_AG)
        df_a["date"]=pd.to_datetime(df_a["Date (Segment)"],errors="coerce")
        df_a["spend"]=to_num(df_a["Cost (Spend, Amount Spent)"])
        df_a["conv"]=to_num(df_a["All Conversions"])
        df_a["clicks"]=to_num(df_a["Clicks"])
        df_a["age"]=df_a["Age (Ad Group Criterion)"].map(AGE_MAP).fillna(df_a["Age (Ad Group Criterion)"].astype(str))
        df_a=df_a.dropna(subset=["date"])
    except Exception as e: print(f"  Aviso Age: {e}"); df_a=pd.DataFrame()
    try:
        df_g=pd.read_csv(URL_GOOGLE_GE)
        df_g["date"]=pd.to_datetime(df_g["Date (Segment)"],errors="coerce")
        df_g["spend"]=to_num(df_g["Cost (Spend, Amount Spent)"])
        df_g["conv"]=to_num(df_g["All Conversions"])
        df_g["gender"]=df_g["Gender (Ad Group Criterion)"].str.lower()
        df_g=df_g.dropna(subset=["date"])
    except Exception as e: print(f"  Aviso Gender: {e}"); df_g=pd.DataFrame()
    AGE_ORDER=["18-24","25-34","35-44","45-54","55-64","65+"]
    def bd(pa, pg):
        aa=pa[pa["age"].isin(AGE_ORDER)].groupby("age").agg(spend=("spend","sum"),conv=("conv","sum")).reset_index()
        aa["_o"]=aa["age"].apply(lambda x:AGE_ORDER.index(x) if x in AGE_ORDER else 99)
        aa=aa[aa["spend"]>0].sort_values("_o")
        aa["cpl"]=(aa["spend"]/aa["conv"]).where(aa["conv"]>0).round(2)
        ga=pg[pg["gender"].isin(["female","male"])].groupby("gender").agg(spend=("spend","sum"),conv=("conv","sum")).reset_index()
        ga=ga[ga["spend"]>0].sort_values("conv",ascending=False)
        ga["cpl"]=(ga["spend"]/ga["conv"]).where(ga["conv"]>0).round(2)
        def tl(df2,dim): return [{"n":str(r[dim]),"spend":round(float(r["spend"]),2),"conv":round(float(r["conv"]),2),"cpl":safe(r["cpl"])} for _,r in df2.iterrows()]
        return {"age":tl(aa,"age"),"gender":tl(ga,"gender")}
    result={}
    def filt(dfa,dfg,start,end):
        pa=dfa[(dfa["date"]>=start)&(dfa["date"]<=end)] if len(dfa)>0 else dfa
        pg=dfg[(dfg["date"]>=start)&(dfg["date"]<=end)] if len(dfg)>0 else dfg
        return bd(pa,pg)
    result["1"]=filt(df_a,df_g,ontem,ontem)
    for n in [7,14,30]: result[str(n)]=filt(df_a,df_g,hoje-pd.Timedelta(days=n-1),hoje)
    result["all"]=bd(df_a,df_g)
    return result

# ══ SEO ═══════════════════════════════════════════════

def meta_monthly(df):
    PT_MONTHS={"Jan":"Jan","Feb":"Fev","Mar":"Mar","Apr":"Abr","May":"Mai",
                "Jun":"Jun","Jul":"Jul","Aug":"Ago","Sep":"Set","Oct":"Out","Nov":"Nov","Dec":"Dez"}
    df=df.copy(); df["ym"]=df["date"].dt.to_period("M")
    months=sorted(df["ym"].unique())
    out={"lbl":[],"totalS":[],"totalL":[],"cplG":[],"cpmG":[],"ctrG":[],"camps":[]}
    for m in months:
        p=df[df["ym"]==m]
        sp=round(float(p["spend"].sum()),2); ld=int(p["leads"].sum())
        imp=float(p["impressions"].sum()); lc=float(p["link_clicks"].sum())
        raw_lbl=pd.Period(m,"M").strftime("%b/%y")
        pt_lbl=PT_MONTHS.get(raw_lbl[:3],raw_lbl[:3])+raw_lbl[3:]
        out["lbl"].append(pt_lbl); out["totalS"].append(sp); out["totalL"].append(ld)
        out["cplG"].append(round(sp/ld,2) if ld>0 else None)
        out["cpmG"].append(round(sp/imp*1000,2) if imp>0 else None)
        out["ctrG"].append(round(lc/imp*100,2) if imp>0 else None)
        ag=p.groupby("campaign").agg(spend=("spend","sum"),leads=("leads","sum"),
            impressions=("impressions","sum"),link_clicks=("link_clicks","sum")).reset_index()
        for _,r in ag.iterrows():
            out["camps"].append({"n":str(r["campaign"]),"spend":round(float(r["spend"]),2),
                "leads":int(r["leads"]),"imp":int(r["impressions"]),"lc":int(r["link_clicks"])})
    print(f"     Meta Mensal: {len(months)} meses")
    return out

def google_monthly(df):
    PT_MONTHS={"Jan":"Jan","Feb":"Fev","Mar":"Mar","Apr":"Abr","May":"Mai",
                "Jun":"Jun","Jul":"Jul","Aug":"Ago","Sep":"Set","Oct":"Out","Nov":"Nov","Dec":"Dez"}
    df=df.copy(); df["ym"]=df["date"].dt.to_period("M")
    months=sorted(df["ym"].unique())
    out={"lbl":[],"totalS":[],"totalConv":[],"cpaG":[],"cpcG":[],"ctrG":[],"camps":[]}
    for m in months:
        p=df[df["ym"]==m]
        sp=round(float(p["spend"].sum()),2); cv=round(float(p["conversions"].sum()),2)
        cl=int(p["clicks"].sum()); imp=int(p["impressions"].sum())
        raw_lbl=pd.Period(m,"M").strftime("%b/%y")
        pt_lbl=PT_MONTHS.get(raw_lbl[:3],raw_lbl[:3])+raw_lbl[3:]
        out["lbl"].append(pt_lbl); out["totalS"].append(sp); out["totalConv"].append(cv)
        out["cpaG"].append(round(sp/cv,2) if cv>0 else None)
        out["cpcG"].append(round(sp/cl,2) if cl>0 else None)
        out["ctrG"].append(round(cl/imp*100,2) if imp>0 else None)
        ag=p.groupby("campaign").agg(spend=("spend","sum"),conversions=("conversions","sum"),
            clicks=("clicks","sum"),impressions=("impressions","sum")).reset_index()
        for _,r in ag.iterrows():
            out["camps"].append({"n":str(r["campaign"]),"spend":round(float(r["spend"]),2),
                "conv":round(float(r["conversions"]),2),"clicks":int(r["clicks"]),"imp":int(r["impressions"])})
    print(f"     Google Mensal: {len(months)} meses")
    return out

def load_pesquisa():
    print("  Lendo pesquisa..."); return pd.read_csv(sheet_url("Pesquisa"))

def pesquisa_process(df, total_leads):
    UTM_COLS=["utm_source","utm_medium","utm_campaign","utm_content"]
    SKIP_COLS=set(UTM_COLS+["Carimbo de data/hora","Timestamp","Email","email",
                             "Qual seu e-mail de cadastro no evento?",
                             "Qual seu primeiro nome?","Qual seu whatsapp?",
                             "Nome","nome","ID","id","Unnamed: 0"])
    PERGUNTAS=[c for c in df.columns
               if c not in SKIP_COLS and not c.lower().startswith("unnamed")
               and str(c).strip() and pd.api.types.is_string_dtype(df[c])
               and df[c].nunique()<=50]
    graficos=[]
    for p in PERGUNTAS:
        if p not in df.columns: continue
        vc=df[p].value_counts(); total=vc.sum()
        graficos.append({"pergunta":p,"opcoes":[{"label":str(k),"qtd":int(v),"pct":round(v/total*100,1)} for k,v in vc.items()]})
    filtros={}
    for col in UTM_COLS:
        if col in df.columns:
            filtros[col]=sorted([v for v in df[col].dropna().unique().tolist() if v and str(v)!="nan"])
    rows=[]
    for _,r in df.iterrows():
        row={}
        for p in PERGUNTAS: row[p]=str(r[p]) if p in df.columns and pd.notna(r.get(p)) else None
        for col in UTM_COLS: row[col]=str(r[col]) if col in df.columns and pd.notna(r.get(col)) else None
        rows.append(row)
    return {"total":len(df),"total_leads":int(total_leads),"graficos":graficos,"filtros":filtros,"rows":rows,"perguntas":PERGUNTAS}

# ══ INJEÇÃO ════════════════════════════════════════════
def replace_js_const(html, name, value):
    """Substitui 'const NAME = <valor>;' no HTML, mesmo com objetos/arrays aninhados."""
    replacement = f"const {name} = {json.dumps(value, ensure_ascii=False)};"
    # Encontrar a declaração const NAME =
    pattern_start = re.compile(rf"const {name}\s*=\s*")
    m = pattern_start.search(html)
    if not m:
        print(f"  AVISO: não encontrou const {name}")
        return html
    start = m.start()
    val_start = m.end()
    # Avançar até o fim do valor (balancear { } e [ ])
    i = val_start
    depth = 0
    in_str = False
    str_char = None
    while i < len(html):
        ch = html[i]
        if in_str:
            if ch == '\\': i += 2; continue
            if ch == str_char: in_str = False
        else:
            if ch in ('"', "'", '`'): in_str = True; str_char = ch
            elif ch in ('{', '['): depth += 1
            elif ch in ('}', ']'): depth -= 1
            elif ch == ';' and depth == 0: break
        i += 1
    end = i + 1  # incluir o ;
    html = html[:start] + replacement + html[end:]
    return html

def inject_all(tpl, meta_k, meta_d, meta_dc, meta_raw_c, meta_t, meta_bd, meta_month, pes,
               g_daily, g_kpis, g_camps, g_kw, g_bd, g_month, g_raw,
):
    html=Path(tpl).read_text(encoding="utf-8")
    # Meta
    html=replace_js_const(html,"META_KPIS",     meta_k)
    html=replace_js_const(html,"META_DAILY",     meta_d)
    html=replace_js_const(html,"META_DAILY_CAMPS", meta_dc)
    html=replace_js_const(html,"META_RAW_CAMP",  meta_raw_c)
    html=replace_js_const(html,"META_TABLES",    meta_t)
    html=replace_js_const(html,"META_BD",        meta_bd)
    html=replace_js_const(html,"META_MONTHLY",   meta_month)
    html=replace_js_const(html,"PESQUISA", pes if USAR_PESQUISA else False)
    html=replace_js_const(html,"DATA_GERACAO", date.today().strftime("%Y-%m-%d"))
    # Google
    html=replace_js_const(html,"GOOGLE_DAILY",   g_daily)
    html=replace_js_const(html,"GOOGLE_KPIS",    g_kpis)
    html=replace_js_const(html,"GOOGLE_CAMPS",   g_camps)
    html=replace_js_const(html,"GOOGLE_KW",      g_kw)
    html=replace_js_const(html,"GOOGLE_BD",      g_bd)
    html=replace_js_const(html,"GOOGLE_MONTHLY", g_month)
    html=replace_js_const(html,"GOOGLE_RAW",     g_raw)
CPL_BOM          = 40.0
CPL_MEDIO        = 45.0
    for k,v in [("LANCAMENTO_COD",f"'{LANCAMENTO_COD}'"),("NOME_CLIENTE",f"'{NOME_CLIENTE}'"),
                ("LOGO_LETRA",f"'{LOGO_LETRA}'"),("COR_ACENTO",f"'{COR_ACENTO}'"),
CPL_MEDIO        = 45.0
CTR_MEDIO        = 0.4
CR_MEDIO         = 60.0
TX_CONV_MEDIO    = 2.0
                ("CPM_BOM",str(CPM_BOM)),("CPM_MEDIO",str(CPM_MEDIO))]:
        html=re.sub(rf"const {k}\s*=\s*[^;]+;",f"const {k}={v};",html,count=1)
    html=re.sub(r"\d{2}/\d{2}/\d{4} · via planilha",date.today().strftime("%d/%m/%Y")+" · via planilha",html)
    return html

# ══ MAIN ═══════════════════════════════════════════════
def main():
    print("="*60)
    print(f"Dashboard Lançamento Gratuito v2 (All Conv) — {NOME_CLIENTE} / {LANCAMENTO_COD or 'Todos'}")
    print("="*60)
    img_dir=Path("imgs"); img_dir.mkdir(exist_ok=True)

    print("\n[META ADS]")
    df_meta=load_meta()
    m_k=meta_kpis(df_meta)
    m_d=meta_daily(df_meta)
    m_dc=meta_daily_camps(df_meta)
    m_raw=meta_raw(df_meta)
    m_t=meta_tables(df_meta,img_dir)
    m_bd=meta_breakdowns(df_meta)
    m_month=meta_monthly(df_meta)
    total_leads=m_k["lct"]["leads"] if LANCAMENTO_COD else m_k["all"]["leads"]
    print(f"  ✓ {total_leads} leads | R$ {m_k['lct']['spend']:,.2f} invest.")

    print("\n[GOOGLE ADS]")
    try:
        df_google=load_google()
        g_daily=google_daily(df_google)
        g_kpis=google_kpis(df_google)
        g_camps=google_camps(df_google)
        g_kw=google_keywords(df_google)
        g_bd=google_breakdowns(df_google)
        g_month=google_monthly(df_google)
        g_raw=google_raw(df_google)
        print(f"  ✓ {df_google['conversions'].sum():.0f} conv. | R$ {df_google['spend'].sum():,.2f} invest.")
    except Exception as e:
        print(f"  Aviso Google: {e}")
        g_daily={"days":[],"spend":[],"conversions":[],"cpa":[],"ctr":[],"cpc":[]}
        g_kpis={}; g_camps={}; g_kw={}; g_bd={}
        g_month={"lbl":[],"totalS":[],"totalConv":[],"cpaG":[],"cpcG":[],"ctrG":[],"camps":[]}
        g_raw=[]

    print("\n[PESQUISA]")
    if USAR_PESQUISA:
        df_pes=load_pesquisa()
        pes=pesquisa_process(df_pes, total_leads)
        print(f"  ✓ {pes['total']} respostas")
    else:
        pes=None
        print("  (desativada)")

    print("\n[HTML]")
    if not Path(TEMPLATE_FILE).exists():
        print(f"  ERRO: {TEMPLATE_FILE} não encontrado"); return
    html=inject_all(TEMPLATE_FILE,m_k,m_d,m_dc,m_raw,m_t,m_bd,m_month,pes,
                    g_daily,g_kpis,g_camps,g_kw,g_bd,g_month,g_raw,
)
    # Diagnóstico — verificar se constantes foram injetadas
    checks = ["GOOGLE_DAILY","GOOGLE_KPIS","GOOGLE_CAMPS","META_MONTHLY"]
    for c in checks:
        idx = html.find(f"const {c} =")
        snippet = html[idx+len(f"const {c} ="):idx+len(f"const {c} =")+30] if idx>=0 else "NÃO ENCONTRADO"
        status = "✓" if "null" not in snippet[:6] and snippet.strip()[:1] in ('{','[','"','0','1','2','3','4','5','6','7','8','9','t','f') else "✗ null"
        print(f"  {status} {c}: {snippet.strip()[:40]}")
    Path(OUTPUT_FILE).write_text(html,encoding="utf-8")
    print(f"  ✓ {OUTPUT_FILE} ({len(html)//1024}KB)")

    data_json={"cliente":NOME_CLIENTE,"cor":COR_ACENTO,"letra":LOGO_LETRA,
               "lancamento":LANCAMENTO_COD,"atualizado":date.today().strftime("%d/%m/%Y"),
               "kpis":{"spend":m_k["lct"].get("spend"),"leads":m_k["lct"].get("leads"),"cpl":m_k["lct"].get("cpl")}}
    Path("data.json").write_text(json.dumps(data_json,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"  ✓ data.json\n{'='*60}")

if __name__=="__main__":
    main()
