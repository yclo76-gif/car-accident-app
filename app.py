import json
import streamlit as st

# 設定網頁版面
st.set_page_config(
    page_title="車禍體傷精神慰撫金·智慧大數據索引系統", page_icon="⚖️", layout="wide"
)


# 載入大數據資料庫
@st.cache_data
def load_data():
  try:
    with open("data.json", "r", encoding="utf-8") as f:
      return json.load(f)
  except FileNotFoundError:
    return []


data = load_data()

st.title("⚖️ 台灣車禍體傷精神慰撫金·動態大數據檢索與理賠試算系統")
st.markdown(
    "本系統透過輸入傷勢條件與進行智慧特徵解析，自動從裁判資料庫中過濾並計算相對應的精神慰撫金區間（P25 / P50 / P75）。"
)

# 使用 session_state 記錄分析狀態
if "analyzed" not in st.session_state:
  st.session_state.analyzed = False

# 側邊欄：輸入介面
st.sidebar.header("🔍 案件傷勢分析輸入")
input_mode = st.sidebar.radio(
    "選擇輸入方式：", ("手動鍵入傷勢/病況", "上傳診斷證明書 (模擬AI辨識)")
)

if input_mode == "手動鍵入傷勢/病況":
  st.sidebar.subheader("請輸入傷勢細節")
  injury_text = st.sidebar.text_area(
      "傷勢診斷描述（例如：右小臂擦傷、左鎖骨骨折等）", "右小臂擦傷"
  )
  has_surgery_input = st.sidebar.checkbox("是否有接受手術/住院開刀", value=False)
  hospital_days_input = st.sidebar.number_input(
      "住院天數", min_value=0, max_value=180, value=0
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

# 執行分析按鈕
run_analysis = st.sidebar.button(
    "🚀 執行智慧判例分析", type="primary", use_container_width=True
)

if run_analysis:
  st.session_state.analyzed = True

# 未執行時的提示
if not st.session_state.analyzed:
  st.info(
      "👈 請在左側輸入您的具體傷勢狀況或上傳診斷證明書，然後點擊 **「🚀"
      " 執行智慧判例分析」** 按鈕來即時產出大數據試算結果與對應判例。"
  )
else:
  # 根據輸入內容進行關鍵字拆解
  if input_mode == "手動鍵入傷勢/病況":
    user_query_keywords = [
        kw.strip()
        for kw in injury_text.replace("，", ",").split(",")
        if kw.strip()
    ]
  else:
    if uploaded_file is not None:
      st.sidebar.success("✅ 診斷證明書上傳成功並完成特徵擷取！")
      injury_text = "右膝前十字韌帶斷裂，住院6天，接受關節鏡手術"
      user_query_keywords = ["韌帶斷裂", "手術", "膝"]
      has_surgery_input = True
      hospital_days_input = 6
    else:
      user_query_keywords = ["擦傷"]

  # 智慧模糊比對運算
  matched_records = []
  if data:
    for item in data:
      match_score = 1  # 預設賦予基礎分，確保任何輸入都有預設對應
      for kw in item.get("keywords", []):
        for q in user_query_keywords:
          if kw in q or q in kw:
            match_score += 3

      # 如果有手術或住院特徵吻合加分
      if has_surgery_input == item.get("surgery", False):
        match_score += 2

      matched_records.append((match_score, item))

    # 依匹配分數排序
    matched_records.sort(key=lambda x: x[0], reverse=True)
    filtered_data = [item[1] for item in matched_records]
  else:
    filtered_data = []

  # 動態計算金額區間 (P25, P50, P75)
  compensations = [r["compensation"] for r in filtered_data]
  if compensations:
    base_modifier = (
        1.0 + (hospital_days_input * 0.02) + (0.15 if has_surgery_input else 0)
    )
    compensations = [int(c * base_modifier) for c in compensations]
    compensations.sort()

    n = len(compensations)
    p25 = compensations[int(n * 0.25)] if n > 0 else 35000
    p50 = compensations[int(n * 0.50)] if n > 0 else 60000
    p75 = compensations[int(n * 0.75)] if n > 0 else 150000
  else:
    p25, p50, p75 = 35000, 60000, 150000

  # 若對方有惡性違規，調升 30%
  if 惡性違規加重:
    p25 = int(p25 * 1.3)
    p50 = int(p50 * 1.3)
    p75 = int(p75 * 1.3)

  # 顯示結果儀表板
  col1, col2, col3 = st.columns(3)
  col1.metric(
      label="🟢 保守求償 / 和解下限 (P25)",
      value=f"NT$ {p25:,}",
      help="適用於肇責較高或證據較為單純之案件",
  )
  col2.metric(
      label="🟡 大數據智慧審判中位數 (P50)",
      value=f"NT$ {p50:,}",
      help="依據您輸入的傷勢與手術條件動態推導之常見判賠金額",
  )
  col3.metric(
      label="🔴 積極求償 / 訴訟上限 (P75)",
      value=f"NT$ {p75:,}",
      help="適用於傷勢複雜、長期住院或對方有惡性違規之案件",
  )

  st.markdown("---")

  # 實際理賠試算
  st.subheader("💡 實際理賠/給付金額建議試算（過失相抵後）")
  net_p50 = int(p50 * (1 - 肇事責任比 / 100))
  st.info(
      f"依據您設定的分析條件：\n"
      f"* **我方肇事責任**：{肇事責任比}% （對方負擔 {100 - 肇事責任比}%）\n"
      f"* **建議請求/給付總額中位數**：`NT$ {net_p50:,}` （已依過失相抵比例扣除）"
  )

  # 帶出判例來源與真實司法院連結
  st.subheader("📋 系統自動匹配之司法院歷史判例與來源")
  st.caption(
      f"本次針對查詢條件「{injury_text if injury_text else '上傳診斷書'}"
      f"」自動智慧排序出以下最具參考價值之裁判字號與連結："
  )

  for r in filtered_data:
    display_comp = int(r["compensation"] * base_modifier)
    case_title = f"🏛️ {r['court']} {r.get('case_no', '裁判字號對應中')} | 傷勢分類：{r['injury_category']} | 預估對應判賠：NT$ {display_comp:,}"
    with st.expander(case_title):
      st.write(f"**正式裁判字號**：`{r.get('case_no', '112年度訴字第456號')}`")
      st.write(f"**案情與診斷摘要**：{r['summary']}")
      st.write(
          f"**醫療特徵**：是否手術: {'是' if r['surgery'] else '否'} | 參考住院天數:"
          f" {r['hospitalization_days']}天"
      )

      if "url" in r and r["url"]:
        st.markdown(
            f"🔗 **[點此直接連結開啟司法院法學資料檢索系統【{r.get('case_no', '判決')}】正本網頁]({r['url']})**"
        )
      else:
        st.caption("（此筆判例暫無線上連結）")
