import json
import os
import pandas as pd
from PIL import Image
import streamlit as st
from google import genai

# ページの設定
st.set_page_config(
    page_title="領収書自動読み取り＆青色申告アプリ", page_icon="🧾", layout="wide"
)

st.title("🧾 領収書自動読み取り ＆ 青色申告管理アプリ")
st.write(
    "スマホやPCからレシート・領収書の画像をアップロードすると、AIが自動で解析して青色申告用の帳簿データを構築します。"
)

# セッション状態の初期化
if "receipts_data" not in st.session_state:
  st.session_state.receipts_data = []


# メイン画面：画像アップロード
uploaded_file = st.file_uploader(
    "領収書・レシートの画像を選択してください (JPEG / PNG)",
    type=["jpg", "jpeg", "png"],
)

if uploaded_file is not None:
  col1, col2 = st.columns([1, 1])
  with col1:
    st.subheader("アップロードされた画像")
    image = Image.open(uploaded_file)
    st.image(image, use_column_width=True)

  with col2:
    st.subheader("AI解析コントロール")
    if not api_key or api_key == "AIzaSy...":
      st.warning(
          "⚠️ コード内の FIXED_API_KEY に正しい Gemini APIキーを設定してください。",
          icon="⚠️",
      )
    else:
      if st.button("🚀 領収書をAIで解析して追加", type="primary"):
        with st.spinner("AIが領収書を読み取っています..."):
          try:
            client = genai.Client(api_key=api_key)
            prompt = """
            あなたは優秀な経理アシスタント兼AI税理士です。
            提供された領収書・レシートの画像から、以下のJSONフォーマットのルールに従って正確にデータを抽出してください。
            【抽出ルール】
            - date: 日付 (YYYY-MM-DD形式。読み取れない場合は直近の推定日または本日の日付)
            - vendor: 支払先（店舗名・会社名）
            - amount: 合計金額（数字のみ、カンマや「円」は除外）
            - account_title: 勘定科目（日本の個人事業主の青色申告を想定し、以下のいずれかに最も適したものを自動判定：「消耗品費」「旅費交通費」「接待交際費」「通信費」「水道光熱費」「地代家賃」「新聞図書費」「雑費」）
            - description: 摘要（購入した品目や内容のメモ）
            必ず以下のJSON形式のみを出力してください。
            {
              "date": "YYYY-MM-DD",
              "vendor": "支払先名称",
              "amount": 0000,
              "account_title": "勘定科目",
              "description": "摘要"
            }
            """
            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=[image, prompt]
            )
            response_text = response.text.strip()
            if response_text.startswith("```json"):
              response_text = response_text[7:]
            if response_text.endswith("```"):
              response_text = response_text[:-3]

            parsed_data = json.loads(response_text.strip())
            st.session_state.receipts_data.append(parsed_data)
            st.success("✅ 読み取りとデータ追加が完了しました！")
            st.rerun()

          except Exception as e:
            st.error(f"❌ エラーが発生しました: {e}")

# データ一覧と集計
st.markdown("---")
st.subheader("📊 登録済み経費データ一覧")

if len(st.session_state.receipts_data) > 0:
  df = pd.DataFrame(st.session_state.receipts_data)
  display_df = df[["date", "vendor", "amount", "account_title", "description"]].copy()
  display_df.columns = ["日付", "支払先", "金額 (円)", "勘定科目", "摘要"]
  edited_df = st.data_editor(display_df, num_rows="dynamic", use_container_width=True)

  st.markdown("### 📈 勘定科目別 集計金額")
  summary_df = edited_df.groupby("勘定科目")["金額 (円)"].sum().reset_index()
  st.dataframe(summary_df, use_container_width=True)

  total_amount = edited_df["金額 (円)"].sum()
  st.metric(label="💰 経費合計金額", value=f"{total_amount:,} 円")

  csv = edited_df.to_csv(index=False).encode("utf-8-sig")
  st.download_button(
      label="📥 CSVファイルとしてダウンロード（会計ソフト取込用）",
      data=csv,
      file_name="blue_return_expenses.csv",
      mime="text/csv",
  )

  if st.button("🗑️ データをすべてリセット"):
    st.session_state.receipts_data = []
    st.rerun()
else:
  st.info(
      "💡 まだデータが登録されていません。上部から領収書画像をアップロードしてください。"
  )