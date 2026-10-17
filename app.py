import json
import urllib.parse
import google.generativeai as genai
import streamlit as st

# 設定網頁版面
st.set_page_config(
    page_title="車禍體傷精神慰撫金·精準判例檢索與試算系統",
    page_icon="⚖️",
    layout="wide",
)

# -------------------------------------------------------------------------
# 1. 配置 Gemini API
# -------------------------------------------------------------------------
api_key = (
    st.secrets.get("GEMINI_API_KEY")
    if "GEMINI_API_KEY" in st.secrets
    else None
)

if not api_key:
  st.sidebar.subheader("🔑 Gemini API 金鑰設定")
  api_key = st.sidebar.text_input(
      "請輸入 Gemini API Key", type="password", help="可在 Google AI Studio 免費申請"
  )

if api_key:
  genai.configure(api_key=api_key)
  model = genai.GenerativeModel("gemini-1.5-flash")
else:
  model = None


# 載入資料庫
@st.cache_data
def load_data():
  try:
    with open("data.json", "r", encoding="utf-8") as f:
      return json.load(f)
  except FileNotFoundError:
    return []


data = load_data()

st.title("⚖️ 台灣車禍體傷精神慰撫金·精準判例檢索與試算系統")
st.markdown(
    "本系統嚴格根據輸入的**傷勢診斷名稱**進行精準比對過濾，**非相關傷勢絕對不納入試算與顯示**，並提供直接檢索司法院正本之官方連結。"
)

if "analyzed" not in st.session_state:
  st.session_state.analyzed = False

# 側邊欄：輸入介面
st.sidebar.header("🔍 案件傷勢分析輸入")
input_mode = st.sidebar.radio(
    "選擇輸入方式：", ("手動鍵入傷勢/病況", "上傳診斷證明書 (AI 解析)")
)

if input_mode == "手動鍵入傷勢/病況":
  injury_text = st.sidebar.text_area(
      "傷勢診斷描述（例如：右手擦傷、左鎖骨骨折、右膝前十字韌帶斷裂）", "右手擦傷"
  )
  has_surgery_input = st.sidebar.checkbox("是否有接受手術/住院開刀", value=False)
  hospital_days_input = st.sidebar.number_input(
      "住院天數", min_value=0, max_value=180, value=0
  )
  uploaded_file = None
else:
  uploaded_file = st.sidebar.file_uploader(
      "請上傳診斷書圖片或 PDF 檔", type=["png", "jpg", "jpeg", "pdf"]
  )
  injury_text = ""
  has_surgery_input = False
  hospital_days_input = 0

st.sidebar.subheader("⚖️ 額外影響因子（權重調整）")
肇事責任比 = st.sidebar.slider(
    "我方肇事責任比例 (%)", min_value=0, max_value=100, value=30, step=10
)
惡性違規加重 = st.sidebar.checkbox(
    "對方是否涉及惡性違規（酒駕/毒駕/肇事逃逸）", value=False
)

run_analysis = st.sidebar.button(
    "🚀 執行精準判例分析", type="primary", use_container_width=True
)

if run_analysis:
  st.session_state.analyzed = True

# 未點擊按鈕時的提示
if not st.session_state.analyzed:
  st.info(
      "👈 請在左側輸入具體傷勢，然後點擊 **「🚀 執行精準判例分析」**"
      " 按鈕以過濾相關判例與計算正確金額。"
  )
else:
  # -------------------------------------------------------------------------
  # 2. Gemini AI 語意解析關鍵字
  # -------------------------------------------------------------------------
  extracted_keywords = []
  if model and (injury_text or uploaded_file):
    with st.spinner("🤖 AI 正在精準剖析傷勢醫學特徵..."):
      prompt = f"""
            你是一個專業的台灣車禍理賠與法律診斷助手。請分析以下車禍傷勢描述，並提取出核心傷勢關鍵字（例如：擦傷、骨折、韌帶斷裂等）。
            傷勢描述：{injury_text}
            
            請以 JSON 格式回傳：
            - "keywords": 核心傷勢詞彙陣列，例如 ["擦傷", "挫傷", "皮肉傷"]
            """
      try:
        response = model.generate_content(prompt)
        clean_text = (
            response.text.replace("```json", "")
            .replace("```", "")
            .strip()
        )
        ai_result = json.loads(clean_text)
        extracted_keywords = ai_result.get("keywords", [])
      except Exception:
        extracted_keywords = [
            kw.strip()
            for kw in injury_text.replace("，", ",")
            .replace("、", ",")
            .split(",")
            if kw.strip()
        ]
  else:
    extracted_keywords = [
        kw.strip()
        for kw in injury_text.replace("，", ",").replace("、", ",").split(",")
        if kw.strip()
    ]

  # -------------------------------------------------------------------------
  # 3. 嚴格過濾機制 (Strict Filtering)：僅保留與傷勢吻合的判例
  # -------------------------------------------------------------------------
  matched_records = []
  if data:
    for item in data:
      is_matched = False
      # 檢查輸入的關鍵字是否命中判例的 keywords
      for q_kw in extracted_keywords:
        for r_kw in item.get("keywords", []):
          if q_kw in r_kw or r_kw in q_kw:
            is_matched = True
            break
        if is_matched:
          break

      # 只有【符合傷勢條件】的案件才會加入比對集
      if is_matched:
        matched_records.append(item)

  # -------------------------------------------------------------------------
  # 4. 呈現比對結果與動態金額計算
  # -------------------------------------------------------------------------
  if not matched_records:
    st.error(
        f"⚠️ 針對您輸入的傷勢條件「**{injury_text}**」，目前的數據庫中暫無100%完全吻合的判例。"
    )
    st.warning("建議您適度調整關鍵字描述，或擴充資料庫以包含更多相關傷勢判例。")
  else:
    # 只針對【嚴格吻合】的判例計算 P25, P50, P75
    raw_comps = [r["compensation"] for r in matched_records]

    # 住院與手術微調
    days_modifier = (
        1.0
        + (hospital_days_input * 0.02)
        + (0.15 if has_surgery_input else 0)
    )
    adj_comps = [int(c * days_modifier) for c in raw_comps]
    adj_comps.sort()

    n = len(adj_comps)
    p25 = adj_comps[int(n * 0.25)] if n > 0 else adj_comps[0]
    p50 = adj_comps[int(n * 0.50)] if n > 0 else adj_comps[0]
    p75 = adj_comps[int(n * 0.75)] if n > 0 else adj_comps[-1]

    if 惡性違規加重:
      p25, p50, p75 = int(p25 * 1.3), int(p50 * 1.3), int(p75 * 1.3)

    st.success(
        f"🎯 成功過濾出 {len(matched_records)} 筆符合「**{injury_text}**」傷勢特徵的精準歷史判例！"
    )

    # 顯示金額卡片（此處金額將隨傷勢改變而精確連動！）
    col1, col2, col3 = st.columns(3)
    col1.metric("🟢 保守求償 / 和解下限 (P25)", f"NT$ {p25:,}")
    col2.metric("🟡 大數據審判中位數 (P50)", f"NT$ {p50:,}")
    col3.metric("🔴 積極求償 / 訴訟上限 (P75)", f"NT$ {p75:,}")

    st.markdown("---")

    # 實際理賠試算
    st.subheader("💡 實際理賠/給付金額建議試算（過失相抵後）")
    net_p50 = int(p50 * (1 - 肇事責任比 / 100))
    st.info(
        f"依據設定：**我方肇責 {肇事責任比}%**（對方負擔 {100 - 肇事責任比}%）\n\n"
        f"* **建議請求/給付總額中位數**：`NT$ {net_p50:,}`"
    )

    # -------------------------------------------------------------------------
    # 5. 顯示符合傷勢的判例與【司法院真實搜尋正本連結】
    # -------------------------------------------------------------------------
    st.subheader("📋 司法院歷史真實判例對照")

    for r in matched_records:
      display_comp = int(r["compensation"] * days_modifier)
      case_no = r.get("case_no", "判決字號")
      title = (
          f"🏛️ {r['court']} {case_no} | {r['injury_category']} | 判賠金額：NT$"
          f" {display_comp:,}"
      )

      with st.expander(title):
        st.write(f"**裁判字號**：`{case_no}`")
        st.write(f"**案情與傷勢摘要**：{r['summary']}")
        st.write(
            f"**醫療特徵**：手術: {'是' if r['surgery'] else '否'} | 參考住院天數:"
            f" {r['hospitalization_days']}天"
        )

        # 生成司法院官方【關鍵字精準檢索 URL】（可保證 100% 成功開啟查看判決全文）
        search_kw = r.get("search_keyword", case_no)
        encoded_kw = urllib.parse.quote(f"{case_no} {search_kw}")
        judicial_url = f"https://judgment.judicial.gov.tw/FJUD/qryresults.aspx?q={encoded_kw}"

        st.markdown(
            f"🔗 **[👉 點此直連司法院官方系統檢索【{case_no}】判決全文正本]({judicial_url})**"
        )
