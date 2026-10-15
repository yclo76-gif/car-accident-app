import json
import streamlit as st

# 設定網頁版面
st.set_page_config(
    page_title="車禍體傷精神慰撫金大數據索引系統", page_icon="⚖️", layout="wide"
)


# 載入資料庫
@st.cache_data
def load_data():
  try:
    with open("data.json", "r", encoding="utf-8") as f:
      return json.load(f)
  except FileNotFoundError:
    return []


data = load_data()

st.title("⚖️ 台灣車禍體傷精神慰撫金·大數據檢索與理賠試算系統")
st.markdown(
    "本系統透過司法院裁判大數據分析，協助理賠人員與法務快速評估不同傷勢與手術狀況下的非財產上損害（精神慰撫金）合理區間。"
)

# 使用 session_state 來儲存是否按下「開始分析」按鈕
if "analyzed" not in st.session_state:
  st.session_state.analyzed = False

# 側邊欄：輸入模式與參數設定
st.sidebar.header("🔍 案件傷勢分析輸入")
input_mode = st.sidebar.radio(
    "選擇輸入方式：", ("手動鍵入傷勢/病況", "上傳診斷證明書 (模擬AI辨識)")
)

if input_mode == "手動鍵入傷勢/病況":
  st.sidebar.subheader("請輸入傷勢細節")
  injury_text = st.sidebar.text_area(
      "傷勢診斷描述（例如：右鎖骨骨折、住院4天、接受內固定手術）",
      "右鎖骨骨折, 接受手術",
  )
  has_surgery_input = st.sidebar.checkbox("是否有接受手術/住院開刀", value=True)
  hospital_days_input = st.sidebar.number_input(
      "住院天數", min_value=0, max_value=180, value=4
  )
  uploaded_file = None
else:
  st.sidebar.subheader("上傳診斷證明書")
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

# 🚀 觸發執行按鈕
run_analysis = st.sidebar.button(
    "🚀 開始分析 / 執行大數據檢索", type="primary", use_container_width=True
)

if run_analysis:
  st.session_state.analyzed = True

# 未點擊按鈕時的提示
if not st.session_state.analyzed:
  st.info(
      "👈 請在左側輸入傷勢條件或上傳診斷證明書，然後點擊 **「🚀"
      " 開始分析 / 執行大數據檢索」** 按鈕以推導金額與獲取歷史判例。"
  )
else:
  # 解析關鍵字
  if input_mode == "手動鍵入傷勢/病況":
    user_query_keywords = [
        kw.strip()
        for kw in injury_text.replace("，", ",").split(",")
        if kw.strip()
    ]
  else:
    if uploaded_file is not None:
      st.sidebar.success("✅ 診斷證明書辨識完成！")
      injury_text = "腰椎椎間盤突出併神經壓迫，住院5天，接受手術"
      user_query_keywords = ["椎間盤突出", "神經壓迫", "手術"]
      has_surgery_input = True
      hospital_days_input = 5
    else:
      user_query_keywords = []

  # 比對資料庫
  matched_records = []
  if data:
    for item in data:
      score = 0
      for kw in item.get("keywords", []):
        if any(kw in q for q in user_query_keywords) or (
            q in kw for q in user_query_keywords
        ):
          score += 1
      if score > 0:
        matched_records.append(item)

    if not matched_records:
      matched_records = data
  else:
    st.error("查無資料庫檔案，請確認 data.json 是否存在。")

  # 計算統計區間 (P25, P50, P75)
  compensations = [r["compensation"] for r in matched_records]
  if compensations:
    compensations.sort()
    n = len(compensations)
    p25 = compensations[int(n * 0.25)] if n > 0 else 50000
    p50 = compensations[int(n * 0.50)] if n > 0 else 100000
    p75 = compensations[int(n * 0.75)] if n > 0 else 200000
  else:
    p25, p50, p75 = 50000, 100000, 200000

  # 惡性違規加權
  if 惡性違規加重:
    p25 = int(p25 * 1.3)
    p50 = int(p50 * 1.3)
    p75 = int(p75 * 1.3)

  # 顯示金額卡片
  col1, col2, col3 = st.columns(3)
  col1.metric(
      label="🟢 保守求償 / 和解下限 (P25)",
      value=f"NT$ {p25:,}",
      help="適用於肇責較高或證據較單薄之案件",
  )
  col2.metric(
      label="🟡 大數據審判中位數 (P50)",
      value=f"NT$ {p50:,}",
      help="司法院歷史相似判例中最常見的判賠金額",
  )
  col3.metric(
      label="🔴 積極求償 / 訴訟上限 (P75)",
      value=f"NT$ {p75:,}",
      help="適用於傷勢嚴重、有開刀或對方有酒駕等惡性違規之案件",
  )

  st.markdown("---")

  # 理賠金額試算
  st.subheader("💡 實際理賠/給付金額建議試算")
  net_p50 = int(p50 * (1 - 肇事責任比 / 100))
  st.info(
      f"依據您設定的 **我方肇事責任 {肇事責任比}%**（對方負擔"
      f" {100 - 肇事責任比}%）：\n"
      f"* **建議請求/給付總額中位數**：`NT$ {net_p50:,}` （已依過失相抵比例調整）"
  )

  # 🏛️ 司法院判例列表 (含字號與直連連結)
  st.subheader("📋 司法院歷史相似判例參考庫")
  st.caption(
      f"共檢索出 {len(matched_records)} 筆相似判例，點開即可查看詳情與司法院原始判決連結："
  )

  for r in matched_records:
    case_title = f"🏛️ {r['court']} {r.get('case_no', '')} | 傷勢分類：{r['injury_category']} | 判賠慰撫金：NT$ {r['compensation']:,}"
    with st.expander(case_title):
      st.write(f"**裁判字號**：`{r.get('case_no', '未提供')}`")
      st.write(f"**案情與傷勢摘要**：{r['summary']}")
      st.write(
          f"**醫療狀態**：是否手術開刀:"
          f" {'是' if r['surgery'] else '否'} | 住院天數:"
          f" {r['hospitalization_days']}天"
      )

      if "url" in r and r["url"]:
        st.markdown(
            f"🔗 **[點此直接開啟司法院【{r.get('case_no', '判決內文')}】正本網頁]({r['url']})**"
        )
      else:
        st.caption("（此筆判例暫無線上連結）")
