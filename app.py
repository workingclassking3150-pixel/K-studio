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
st.write("複数のレシート写真をまとめて選択できます。1枚ずつ確実に安全に解析してデータ化します。")

if "receipts_data" not in st.session_state:
    st.session_state.receipts_data = []

# 複数ファイルの選択
uploaded_files = st.file_uploader(
    "レシート・領収書の画像を複数選択してください（複数選択可 / JPEG・PNG）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if uploaded_files:
    st.subheader(f"📁 選択された画像: {len(uploaded_files)}枚")
    
    cols = st.columns(min(len(uploaded_files), 4))
    for idx, uploaded_file in enumerate(uploaded_files):
        with cols[idx % len(cols)]:
            image = Image.open(uploaded_file)
            st.image(image, use_container_width=True, caption=f"画像 {idx+1}")
            
    st.markdown("---")
    
    api_key = ""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass
        
    if not api_key:
        st.error("⚠️ Streamlit Secrets に `GEMINI_API_KEY` が設定されていません。")
    else:
        st.success("🔑 APIキーは正常に読み込まれています。")
        if st.button(f"🚀 選択した {len(uploaded_files)}枚を順番に解析して追加", type="primary"):
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            success_count = 0
            for idx, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"⏳ {idx+1}枚目のレシートを解析中...")
                
                try:
                    image = Image.open(uploaded_file).convert("RGB")
                    # サーバーに負荷をかけないよう、最適な小サイズに圧縮
                    image.thumbnail((800, 800))
                    
                    import io as py_io
                    buffered = py_io.BytesIO()
                    image.save(buffered, format="JPEG", quality=75)
                    img_bytes = buffered.getvalue()
                    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                    
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
                    
                    prompt_text = """
                    あなたはプロの経理アシスタント兼AI税理士です。
                    提供されたレシート画像のデータを以下のJSONフォーマットに従って抽出してください。
                    
                    【抽出ルール】
                    - date: 日付 (YYYY-MM-DD形式)
                    - vendor: 支払先 (店舗名・会社名)
                    - amount: 合計金額 (数字のみの整数)
                    - account_title: 勘定科目 (「消耗品費」「旅費交通費」「接待交際費」「通信費」「水道光熱費」「地代家賃」「新聞図書費」「車両費」「雑費」のいずれか)
                    - description: 摘要 (購入した品目や内容)
                    
                    必ずオブジェクト形式 { ... } で、マークダウンの ```json ... ``` の中に出力してください。
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
                    response = requests.post(url, json=payload, headers=headers, timeout=30)
                    result_json = response.json()
                    
                    if "error" in result_json:
                        err_msg = result_json["error"].get("message", "不明なエラー")
                        st.warning(f"⚠️ {idx+1}枚目スキップ: {err_msg}")
                    elif "candidates" in result_json:
                        response_text = result_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                        
                        if "```json" in response_text:
                            response_text = response_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in response_text:
                            response_text = response_text.split("```")[1].split("```")[0].strip()
                            
                        new_item = json.loads(response_text)
                        
                        if isinstance(new_item, list):
                            st.session_state.receipts_data.extend(new_item)
                        else:
                            st.session_state.receipts_data.append(new_item)
                        success_count += 1
                        
                except Exception as e:
                    st.warning(f"⚠️ {idx+1}枚目でエラーが発生しました: {str(e)}")
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            status_text.empty()
            progress_bar.empty()
            st.success(f"✨ 処理完了！ {success_count}件のレシートデータを追加しました！")
            st.rerun()

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
    st.info("💡 まだデータが登録されていません。上のアップロードボタンから複数枚の写真を選択してください。")
