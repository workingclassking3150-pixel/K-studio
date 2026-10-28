import json
import base64
import requests
import pandas as pd
from PIL import Image
import streamlit as st

st.set_page_config(
    page_title="領収書自動読み取り ＆ 青色申告管理アプリ",
    page_icon="🧾",
    layout="wide"
)

st.title("🧾 領収書自動読み取り ＆ 青色申告管理アプリ")
st.write("複数のレシート・領収書が並んだ画像を一度にアップロードして、AIが一括解析します。")

if "receipts_data" not in st.session_state:
    st.session_state.receipts_data = []

uploaded_file = st.file_uploader(
    "複数のレシートが写った画像をアップロードしてください（JPEG / PNG）",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("アップロードされた画像")
        image = Image.open(uploaded_file)
        st.image(image, use_container_width=True)
        
    with col2:
        st.subheader("AI解析コントロール")
        
        api_key = ""
        try:
            api_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            pass
            
        if not api_key:
            st.error("⚠️ Streamlit Secrets に `GEMINI_API_KEY` が設定されていません。")
        else:
            st.success("🔑 APIキーは正常に読み込まれています。")
            if st.button("🚀 まとめてAI解析して追加", type="primary"):
                with st.spinner("多数のレシートをAIが一括解析しています..."):
                    try:
                        # 複数枚の画像が重くならないよう、さらにピクセル数を抑えて軽量化
                        image.thumbnail((1200, 1200))
                        
                        import io as py_io
                        buffered = py_io.BytesIO()
                        image.save(buffered, format="JPEG", quality=75)
                        img_bytes = buffered.getvalue()
                        img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                        
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
                        
                        prompt_text = """
                        あなたはプロの経理アシスタント兼AI税理士です。
                        提供された画像には、複数の領収書やレシートが並べて撮影されています。
                        写っているすべてのレシートをもれなく認識し、それぞれのデータを以下のJSONフォーマットのルールに従って配列（リスト）形式で抽出してください。
                        
                        【抽出ルール】
                        - date: 日付 (YYYY-MM-DD形式)
                        - vendor: 支払先 (店舗名・会社名)
                        - amount: 合計金額 (数字のみの整数)
                        - account_title: 勘定科目 (「消耗品費」「旅費交通費」「接待交際費」「通信費」「水道光熱費」「地代家賃」「新聞図書費」「車両費」「雑費」のいずれか)
                        - description: 摘要 (購入した品目や内容)
                        
                        必ず以下のJSON配列形式のみを ```json ... ``` の中に出力してください。
                        [
                          {
                            "date": "YYYY-MM-DD",
                            "vendor": "支払先名称",
                            "amount": 1000,
                            "account_title": "消耗品費",
                            "description": "購入品目"
                          }
                        ]
                        """
                        
                        payload = {
                            "contents": [
                                {
                                    "parts": [
                                        {"text": prompt_text},
                                        {
                                            "inline_data": {
                                                "mime_type": "image/jpeg",
                                                "data": img_base64
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                        
                        headers = {"Content-Type": "application/json"}
                        response = requests.post(url, json=payload, headers=headers)
                        result_json = response.json()
                        
                        if "error" in result_json:
                            err_msg = result_json["error"].get("message", "不明なエラー")
                            st.error(f"❌ APIエラー: {err_msg}")
                        elif "candidates" in result_json:
                            response_text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                            
                            if "```json" in response_text:
                                response_text = response_text.split("```json")[1].split("```")[0].strip()
                            elif "```" in response_text:
                                response_text = response_text.split("```")[1].split("```")[0].strip()
                                
                            new_items = json.loads(response_text)
                            
                            if isinstance(new_items, list):
                                st.session_state.receipts_data.extend(new_items)
                                st.success(f"✨ {len(new_items)}件のレシートデータをまとめて追加しました！")
                            else:
                                st.session_state.receipts_data.append(new_items)
                                st.success("✨ レシートデータを追加しました！")
                        else:
                            st.error("❌ 応答形式が予期せぬものです。")
                            
                    except Exception as e:
                        st.error(f"❌ エラーが発生しました: {str(e)}")

st.markdown("---")
st.subheader("📊 登録済み経費データ一覧 & やよい連携")

if len(st.session_state.receipts_data) > 0:
    df = pd.DataFrame(st.session_state.receipts_data)
    st.dataframe(df, use_container_width=True)
    
    csv_data = []
    for item in st.session_state.receipts_data:
        csv_data.append({
            "取引日": item.get("date", ""),
            "借方勘定科目": item.get("account_title", "消耗品費"),
            "借方金額": item.get("amount", 0),
            "貸方勘定科目": "現金",
            "貸方金額": item.get("amount", 0),
            "摘要": f"{item.get('vendor', '')} - {item.get('description', '')}"
        })
    
    df_yayoi = pd.DataFrame(csv_data)
    csv_string = df_yayoi.to_csv(index=False)
    csv_bytes = csv_string.encode("shift_jis", errors="ignore")
    
    col_dl, col_cl = st.columns([1, 1])
    with col_dl:
        st.download_button(
            label="📥 やよいの青色申告用CSVをダウンロード",
            data=csv_bytes,
            file_name="yayoi_keikhi.csv",
            mime="text/csv",
            type="primary"
        )
    with col_cl:
        if st.button("🗑️ データをすべてクリア"):
            st.session_state.receipts_data = []
            st.rerun()
else:
    st.info("💡 まだデータが登録されていません。レシート画像をアップロードしてください。")
