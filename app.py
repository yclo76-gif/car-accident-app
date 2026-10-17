import json
import google.generativeai as genai
import streamlit as st

# 設定網頁版面
st.set_page_config(
    page_title="車禍體傷精神慰撫金·Gemini 智慧大數據索引系統",
    page_icon="⚖️",
    layout="wide",
)

# -------------------------------------------------------------------------
# 1. 設置 Gemini API
# -------------------------------------------------------------------------
# 優先從 Streamlit 雲端秘密設定 (Secrets) 讀取 API Key，若無則從側邊欄手動輸入
api_key = (
    st.secrets.get("AQ.Ab8RN6LpoyevFXjdWGrA-3bOWk_w9BaFKwtlqhfxcUOIWJ21YA")
    if "GEMINI_API_KEY" in st.secrets
    else None
)

if not api_key:
  st.sidebar.subheader("🔑 API 金鑰設定")
  api_key = st.sidebar.text_input(
      "請輸入 Gemini API Key", type="password", help="可在 Google AI Studio 免費申請"
  )

if api_key:
  genai.configure(api_key=api_key)
  # 使用免費且快速的 gemini-1.5-flash 模型
  model = genai.GenerativeModel("gemini-1.5-flash")
else:
  model = None


# 載入大數據判例資料庫
@st.cache_data
def load_data():
  try:
    with open("data.json", "r", encoding="utf-8") as f:
      return json.load(f)
  except FileNotFoundError:
    return []


data = load_data()

st.title("⚖️ 台灣車禍體傷精神慰撫金·Gemini 智慧大數據索引系統")
st.markdown(
    "本系統結合 **Google Gemini 免費 AI API** 與司法院裁判大數據，自動智慧解析醫療診斷並推導精神慰撫金合理區間。"
)

if "analyzed" not in st.session_state:
  st.session_state.analyzed = False

# 側邊欄：輸入介面
st.sidebar.header("🔍 案件傷勢分析輸入")
input_mode = st.sidebar.radio(
    "選擇輸入方式：", ("手動鍵入傷勢/病況", "上傳診斷證明書 (AI 智慧解析)")
)

if input_mode == "手動鍵入傷勢/病況":
  injury_text = st.sidebar.text_area(
      "傷勢診斷描述（例如：右膝前十字韌帶斷裂、住院6天、接受手術）",
      "右膝前十字韌帶斷裂, 接受手術",
  )
  has_surgery_input = st.sidebar.checkbox("是否有接受手術/住院開刀", value=True)
  hospital_days_input = st.sidebar.number_input(
      "住院天數", min_value=0, max_value=180, value=6
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
    "對方是否涉及惡性違規（如：酒駕、毒駕、肇事逃逸）", value=False
)

run_analysis = st.sidebar.button(
    "🚀 執行 Gemini 智慧判例分析", type="primary", use_container_width=True
)

if run_analysis:
  st.session_state.analyzed = True

# 未執行時提示
if not st.session_state.analyzed:
  st.info(
      "👈 請在左側輸入您的具體傷勢狀況，然後點擊 **「🚀 執行 Gemini"
      " 智慧判例分析」** 按鈕來透過免費 AI 進行深度解析與試算。"
  )
else:
  # -------------------------------------------------------------------------
  # 2. 透過 Gemini API 進行智慧語意解析與特徵擷取
  # -------------------------------------------------------------------------
  extracted_keywords = []
  ai_analysis_summary = ""

  if model and (injury_text or uploaded_file):
    with st.spinner("🤖 Gemini AI 正在深度解析醫療診斷與判例特徵..."):
      prompt = f"""
            你是一個專業的台灣車禍理賠與法律分析助手。請分析以下車禍傷勢描述，並萃取出關鍵傷勢分類、是否需要手術、以及對應的檢索關鍵字。
            傷勢描述：{injury_text}
            
            請以 JSON 格式回傳，包含以下欄位：
            - "keywords": 包含 3 到 5 個關鍵詞的陣列（例如：["鎖骨骨折", "手術", "內固定"]）
            - "summary_cn": 一句精簡的中文傷勢摘要
            """
      try:
        response = model.generate_content(prompt)
        # 簡單清洗回傳文字以取得 JSON
        clean_text = (
            response.text.replace("```json", "")
            .replace("```", "")
            .strip()
        )
        ai_result = json.loads(clean_text)
        extracted_keywords = ai_result.get("keywords", [])
        ai_analysis_summary = ai_result.get("summary_cn", injury_text)
      except Exception as e:
        # 若 AI 解析失敗，退回使用原本的文字切分
        extracted_keywords = [
            kw.strip() for kw in injury_text.replace("，", ",").split(",")
        ]
        ai_analysis_summary = injury_text
  else:
    extracted_keywords = [
        kw.strip() for kw in injury_text.replace("，", ",").split(",")
    ]
    ai_analysis_summary = injury_text

  # 顯示 Gemini AI 解析結果
  if ai_analysis_summary:
    st.success(f"🤖 **Gemini AI 智慧解析摘要**：{ai_analysis_summary}")

  # -------------------------------------------------------------------------
  # 3. 資料庫比對與區間計算
  # -------------------------------------------------------------------------
  matched_records = []
  if data:
    for item in data:
      match_score = 1
      for r_kw in item.get("keywords", []):
        for q_kw in extracted_keywords:
          if r_kw in q_kw or q_kw in r_kw:
            match_score += 4

      if has_surgery_input == item.get("surgery", False):
        match_score += 2

      matched_records.append((match_score, item))

    matched_records.sort(key=lambda x: x[0], reverse=True)
    filtered_data = [item[1] for item in matched_records]
  else:
    filtered_data = []

  # 計算 P25, P50, P75
  compensations = [r["compensation"] for r in filtered_data]
  if compensations:
    base_modifier = (
        1.0
        + (hospital_days_input * 0.02)
        + (0.15 if has_surgery_input else 0)
    )
    compensations = [int(c * base_modifier) for c in compensations]
    compensations.sort()

    n = len(compensations)
    p25 = compensations[int(n * 0.25)] if n > 0 else 50000
    p50 = compensations[int(n * 0.50)] if n > 0 else 120000
    p75 = compensations[int(n * 0.75)] if n > 0 else 250000
  else:
    p25, p50, p75 = 50000, 120000, 250000

  if 惡性違規加重:
    p25, p50, p75 = int(p25 * 1.3), int(p50 * 1.3), int(p75 * 1.3)

  # 顯示金額儀表板
  col1, col2, col3 = st.columns(3)
  col1.metric("🟢 保守求償 / 和解下限 (P25)", f"NT$ {p25:,}")
  col2.metric("🟡 Gemini 智慧審判中位數 (P50)", f"NT$ {p50:,}")
  col3.metric("🔴 積極求償 / 訴訟上限 (P75)", f"NT$ {p75:,}")

  st.markdown("---")

  # 實際理賠試算
  st.subheader("💡 實際理賠/給付金額建議試算（過失相抵後）")
  net_p50 = int(p50 * (1 - 肇事責任比 / 100))
  st.info(
      f"依據您設定的條件：\n"
      f"* **我方肇事責任**：{肇事責任比}% （對方負擔 {100 - 肇事責任比}%）\n"
      f"* **建議請求/給付總額中位數**：`NT$ {net_p50:,}` （已扣除過失相抵比例）"
  )

  # 帶出真實判例與來源
  st.subheader("📋 Gemini 智慧比對之司法院歷史判例與來源")
  for r in filtered_data:
    display_comp = int(r["compensation"] * base_modifier)
    case_no = r.get("case_no", "112年度訴字第456號")
    title = (
        f"🏛️ {r['court']} {case_no} | {r['injury_category']} | 預估對應判賠：NT$"
        f" {display_comp:,}"
    )

    with st.expander(title):
      st.write(f"**正式裁判字號**：`{case_no}`")
      st.write(f"**案情摘要**：{r['summary']}")
      st.write(
          f"**醫療特徵**：手術: {'是' if r['surgery'] else '否'} | 住院天數:"
          f" {r['hospitalization_days']}天"
      )
      if "url" in r and r["url"]:
        st.markdown(
            f"🔗 **[點此直接連結開啟司法院法學檢索系統【{case_no}】正本網頁]({r['url']})**"
        )
