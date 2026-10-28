import json
import base64
import requests
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="領収書自動読み取り ＆ 青色申告管理アプリ",
    page_icon="🧾",
    layout="wide"
)

st.title("🧾 領収書自動読み取り ＆ 青色申告管理アプリ（PDF一括高速版）")
st.write("スマホのスキャンアプリ等で複数枚のレシートを**1つにまとめたPDFファイル**をアップロードしてください。AIが一撃で解析します！")

if "receipts_data" not in st.session_state:
    st.session_state.receipts_data = []

# PDFファイルをアップロード
uploaded_pdf = st.file_uploader(
    "レシートをまとめたPDFファイルを選択してください",
    type=["pdf"]
)

if uploaded_pdf is not None:
    st.success(f"📄 ファイルが選択されました: {uploaded_pdf.name}")
    
    api_key = ""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass
        
    if not api_key:
        st.error("⚠️ Streamlit Secrets に `GEMINI_API_KEY` が設定されていません。")
    else:
        if st.button("🚀 PDFをAIが一括解析する", type="primary"):
            with st.spinner("PDFを解析しています。少々お待ちください..."):
                try:
                    # PDFをバイナリからBase64に変換
                    pdf_bytes = uploaded_pdf.getvalue()
                    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
                    
                    # 安定性の高い gemini-1.5-flash エンドポイント
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                    
                    prompt_text = """
                    あなたはプロの経理アシスタント兼AI税理士です。
                    提供されたPDFファイルに含まれているすべてのレシート・領収書のデータを、もれなく認識して抽出してください。
                    それぞれのデータを以下のJSONフォーマットのルールに従って、必ず配列（リスト）形式ですべて抽出してください。
                    
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
                                            "mime_type": "application/pdf",
                                            "data": pdf_base64
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                    
                    headers = {"Content-Type": "application/json"}
                    response = requests.post(url, json=payload, headers=headers, timeout=60)
                    
                    if response.status_code != 200:
                        st.error(f"❌ HTTPエラー ({response.status_code}): {response.text}")
                    else:
                        result_json = response.json()
                        
                        if "error" in result_json:
                            err_msg = result_json["error"].get("message", "不明なエラー")
                            st.error(f"❌ APIエラー: {err_msg}")
                        elif "candidates" in result_json:
                            candidate = result_json["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                response_text = candidate["content"]["parts"][0]["text"].strip()
                                
                                if "```json" in response_text:
                                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                                elif "```" in response_text:
                                    response_text = response_text.split("```")[1].split("```")[0].strip()
                                    
                                new_items = json.loads(response_text)
                                
                                if isinstance(new_items, list):
                                    st.session_state.receipts_data.extend(new_items)
                                    st.success(f"✨ 処理完了！ {len(new_items)}件のレシートデータを一括追加しました！")
                                else:
                                    st.session_state.receipts_data.append(new_items)
                                    st.success("✨ レシートデータを追加しました！")
                                st.rerun()
                            else:
                                st.error("❌ AIの応答が不完全です。")
                        else:
                            st.error(f"❌ 予期せぬ応答です: {str(result_json)}")
                            
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
    st.info("💡 まだデータが登録されていません。上のアップロードボタンからレシートをまとめたPDFを選択してください。")
