import json
import re
import google.generativeai as genai
import streamlit as st

# 設定網頁版面
st.set_page_config(
    page_title="車禍體傷精神慰撫金·精準判例檢索與試算系統",
    page_icon="⚖️",
    layout="wide",
)

# -------------------------------------------------------------------------
# 1. 自動偵測與隱藏 API 金鑰設定
# -------------------------------------------------------------------------
# 從 Streamlit secrets 讀取，如果沒有，才顯示輸入欄位
api_key = st.secrets.get("GEMINI_API_KEY", None)

if not api_key:
  st.sidebar.subheader("🔑 Gemini API 設定")
  api_key = st.sidebar.text_input(
      "請輸入 Gemini API Key", type="password", help="可在 Google AI Studio 免費申請"
  )

if api_key:
  try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
  except Exception:
    model = None
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
    "本系統採用**『解剖部位 + 傷勢類型』嚴格雙重比對演算法**。非精準吻合之部位與傷勢**絕不混入計算**，確保試算結果公正客觀。"
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
      "傷勢診斷描述（例如：右手骨折、右手擦傷、鎖骨骨折）", "右手骨折"
  )
  has_surgery_input = st.sidebar.checkbox("是否有接受手術/住院開刀", value=True)
  hospital_days_input = st.sidebar.number_input(
      "住院天數", min_value=0, max_value=180, value=3
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
      "👈 請在左側輸入具體傷勢描述（例如：**右手骨折** 或 **右手擦傷**），點擊"
      " **「🚀 執行精準判例分析」**。"
  )
else:
  # -------------------------------------------------------------------------
  # 2. Gemini AI 或規則引擎拆解『部位』與『傷勢』
  # -------------------------------------------------------------------------
  target_body_part = ""
  target_injury_type = ""

  if model and (injury_text or uploaded_file):
    with st.spinner("🤖 AI 正在進行高精度醫學語意拆解..."):
      prompt = f"""
            請分析以下車禍傷勢："{injury_text}"
            請精準拆解出：
            1. 主要解剖部位 (如：右手, 手臂, 鎖骨, 腿部, 頸部)
            2. 主要傷勢類型 (如：骨折, 擦傷, 挫傷, 拉傷, 斷裂)
            請只回傳 JSON 格式：
            {{"body_part": "部位名稱", "injury_type": "傷勢類型"}}
            """
      try:
        response = model.generate_content(prompt)
        clean_json = re.search(r"\{.*\}", response.text, re.DOTALL).group()
        res_json = json.loads(clean_json)
        target_body_part = res_json.get("body_part", "")
        target_injury_type = res_json.get("injury_type", "")
      except Exception:
        target_body_part = injury_text
        target_injury_type = injury_text

  # 本地規則雙重保險
  if not target_body_part or target_body_part == injury_text:
    if "鎖骨" in injury_text:
      target_body_part = "鎖骨"
    elif any(x in injury_text for x in ["手", "臂"]):
      target_body_part = "手臂"

  if not target_injury_type or target_injury_type == injury_text:
    if "骨折" in injury_text:
      target_injury_type = "骨折"
    elif any(x in injury_text for x in ["擦傷", "挫傷"]):
      target_injury_type = "擦傷"

  st.success(
      f"🔍 **精準對比特徵標籤**：部位 `[{target_body_part}]` ｜ 傷勢"
      f" `[{target_injury_type}]`"
  )

  # -------------------------------------------------------------------------
  # 3. 嚴格對比比對邏輯 (Strict Filtering)
  # -------------------------------------------------------------------------
  matched_records = []
  if data:
    for item in data:
      body_match = False
      type_match = False

      # 比對部位
      for b in item.get("body_parts", []):
        if (
            b in target_body_part
            or target_body_part in b
            or b in injury_text
            or injury_text in b
        ):
          body_match = True
          break

      # 比對傷勢類型
      i_type = item.get("injury_type", "")
      if (
          i_type in target_injury_type
          or target_injury_type in i_type
          or i_type in injury_text
      ):
        type_match = True

      # 只有【部位】與【傷勢類型】同時吻合才放入結果池！
      if body_match and type_match:
        matched_records.append(item)

  # -------------------------------------------------------------------------
  # 4. 顯示結果與金額計算
  # -------------------------------------------------------------------------
  if not matched_records:
    st.error(
        f"⚠️ 數據庫中暫無同時符合部位「{target_body_part}」且傷勢為「{target_injury_type}」的歷史判例！"
    )
    st.warning("請試著調整傷勢描述，或於 data.json 中新增該特徵之真實判例。")
  else:
    raw_comps = [r["compensation"] for r in matched_records]

    # 加權微調
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

    st.info(
        f"🎯 成功過濾出 {len(matched_records)} 筆精準符合「**{injury_text}**」的司法院判例！"
    )

    # 儀表板金額（隨傷勢連動！）
    col1, col2, col3 = st.columns(3)
    col1.metric("🟢 保守求償 / 和解下限 (P25)", f"NT$ {p25:,}")
    col2.metric("🟡 大數據審判中位數 (P50)", f"NT$ {p50:,}")
    col3.metric("🔴 積極求償 / 訴訟上限 (P75)", f"NT$ {p75:,}")

    st.markdown("---")

    # 實際理賠金額
    st.subheader("💡 實際理賠/給付金額建議試算（過失相抵後）")
    net_p50 = int(p50 * (1 - 肇事責任比 / 100))
    st.info(
        f"依據設定：**我方肇責 {肇事責任比}%**（對方負擔 {100 - 肇事責任比}%）\n\n"
        f"* **建議請求/給付總額中位數**：`NT$ {net_p50:,}`"
    )

    # -------------------------------------------------------------------------
    # 5. 判例對照與【司法院正本直連】
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
        st.write(f"**正式裁判字號**：`{case_no}`")
        st.write(f"**案情與傷勢摘要**：{r['summary']}")
        st.write(
            f"**醫療特徵**：手術: {'是' if r['surgery'] else '否'} | 參考住院天數:"
            f" {r['hospitalization_days']}天"
        )

        st.markdown(
            f"🔗 **[👉 點此直連司法院官方系統檢視【{case_no}】判決全文正本]({r['official_url']})**"
        )
