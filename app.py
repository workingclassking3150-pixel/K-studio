import json
import os
import pandas as pd
from PIL import Image
import streamlit as st
from google import genai

# ページの初期設定
st.set_page_config(
    page_title="領収書自動読み取り ＆ 青色申告管理アプリ",
    page_icon="🧾",
    layout="wide"
)

st.title("🧾 領収書自動読み取り ＆ 青色申告管理アプリ")
st.write("スマホやPCから複数のレシート・領収書が並んだ画像をアップロードすると、AIが自動で個別に解析して青色申告用の経費データを構築します。")

# セッション状態の初期化
if "receipts_data" not in st.session_state:
    st.session_state.receipts_data = []

# メイン画面：画像アップロード
uploaded_file = st.file_uploader(
    "領収書・レシートの画像をアップロードしてください（JPEG / PNG）",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("アップロードされた画像")
        image = Image.open(uploaded_file)
        st.image(image, use_column_width=True)
        
    with col2:
        st.subheader("AI解析コントロール")
        
        # Streamlit SecretsからAPIキーを取得
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        
        if not api_key:
            st.warning("⚠️ Streamlit Secrets に `GEMINI_API_KEY` が設定されていません。")
        else:
            if st.button("🚀 領収書をAIで解析して追加", type="primary"):
                with st.spinner("AIが複数のレシートを解析しています..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        prompt = """
                        あなたは優秀な経理アシスタント兼AI税理士です。
                        提供された画像内に含まれる【すべての領収書・レシート】を個別にすべて認識し、それぞれのデータを以下のJSONフォーマットのルールに則って抽出してください。
                        レシートが複数枚ある場合は、必ずすべてのレシートの情報を配列（リスト）に含めてください。
                        
                        【抽出ルール】
                        - date: 日付 (YYYY-MM-DD形式。読み取れない場合は直近の推定日または本日の日付)
                        - vendor: 支払先 (店舗名・会社名)
                        - amount: 合計金額 (数字のみ、カンマや「円」は除外)
                        - account_title: 勘定科目 (日本の個人事業主の青色申告を想定し、以下のいずれかに最も適したもの自動判定：「消耗品費」「旅費交通費」「接待交際費」「通信費」「水道光熱費」「地代家賃」「新聞図書費」「雑費」)
                        - description: 摘要 (購入した品目や内容のメモ)
                        
                        必ず以下のJSON配列（リスト）形式のみを出力してください（マークダウンの ```json ... ``` の中に記述してください）。
                        [
                          {
                            "date": "YYYY-MM-DD",
                            "vendor": "支払先名称",
                            "amount": 1000,
                            "account_title": "消耗品費",
                            "description": "購入品目など"
                          }
                        ]
                        """
                        
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[image, prompt]
                        )
                        
                        response_text = response.text.strip()
                        
                        # マークダウンのコードブロックが含まれている場合のクリーニング
                        if "```json" in response_text:
                            response_text = response_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in response_text:
                            response_text = response_text.split("```")[1].split("```")[0].strip()
                            
                        # JSONとしてパース
                        new_items = json.loads(response_text)
                        
                        # リスト形式で追加されるため、まとめてセッションに格納
                        if isinstance(new_items, list):
                            st.session_state.receipts_data.extend(new_items)
                            st.success(f"✨ {len(new_items)}件のレシートデータを正常に読み込みました！")
                        else:
                            st.session_state.receipts_data.append(new_items)
                            st.success("✨ レシートデータを正常に読み込みました！")
                            
                    except Exception as e:
                        st.error(f"❌ 解析エラーが発生しました: {e}")

# 登録済みデータの一覧表示
st.markdown("---")
st.subheader("📊 登録済み経費データ一覧")

if len(st.session_state.receipts_data) > 0:
    df = pd.DataFrame(st.session_state.receipts_data)
    st.dataframe(df, use_container_width=True)
    
    if st.button("🗑️ データをすべてクリア"):
        st.session_state.receipts_data = []
        st.rerun()
else:
    st.info("💡 まだデータが登録されていません。上から複数のレシートが写った画像をアップロードしてください。")