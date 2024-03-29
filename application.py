# Web画面制御
from flask import Flask, request, jsonify, render_template

# json関連
import json

# API Management API呼び出し関連
import requests
from requests.exceptions import RequestException

# AzureOpenAIモデル,AI Search呼び出し関連
import openai
from azure.core.credentials import AzureKeyCredential  
from azure.search.documents import SearchClient  
from azure.search.documents.models import Vector 

## プロキシ認証情報を設定 ローカルデバッグ時
#import os

## Webサービス（Flask）起動
app = Flask(__name__)

### 各種キー設定
# API Management APIの呼び出しURL
api_url = 'https://hekchat-api-managementservice.azure-api.net/rag/'    # 対象APIのBaseURL
Api_Subscription_Key = '3dae31fe25da43bc9a1a3edb603ea2b0'               # 対象APIで使用するサブスクリプションキー

# Azure OpenAIのAPIキー／エンドポイント等を設定する
openai.api_type = 'azure'
openai.api_key = 'e0a5da9b62fa47cd991976f68c0e9521'             # Azure OpenAI のキー（キー１を使用）
openai.api_base = 'https://hekchat-openai.openai.azure.com/'    # Azure OpenAI のエンドポイント
openai.api_version = '2023-07-01-preview'                       # Azure OpenAI のAPIバージョン
gpt_model_name = 'model-gpt-35-turbo-2'                         # ChatGPTのデプロイモデル
embedding_model_name = 'model-text-embedding-ada-002'           # Ada（ベクトル化用）のデプロイモデル

# Azure AI SearchのAPIキー／エンドポイント等を設定する
search_service_endpoint = 'https://jahqnaservice01-ascv4pcsvl4cowq.search.windows.net'  # Azure AI SearchのURL
search_service_api_key = 'EA4FCAC1E496E0EC100DAFA768E33C30'                             # Azure AI SearchのAPIキー（プライマリ管理者キーを使用）
#index_name = 'test-sera'                                                                # 作成ベクトル化INDEX名
index_name = 'vector-nagao-kitei'                                                       # 作成ベクトル化INDEX名
# Azure AI Searchへの認証に使用される資格情報を生成生成
credential = AzureKeyCredential(search_service_api_key)

### プロキシ認証情報を設定 ローカルデバッグ時
## requests用プロキシ設定
#proxies = {
#    "http": "http://sera:Ej3AR1MH,<@172.16.1.23:15080",
#    "https": "http://sera:Ej3AR1MH,<@172.16.1.23:15080"
#}
## openai用プロキシ設定
#os.environ["http_proxy"] = "http://sera:Ej3AR1MH,<@172.16.1.23:15080"
#os.environ["https_proxy"] = "http://sera:Ej3AR1MH,<@172.16.1.23:15080"

## メイン処理
# Web画面処理 初期表示時
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')    # テンプレートHTMLを表示

# Web画面処理 質問文入力時
@app.route('/chat', methods=['POST'])
def chat():
    # リクエストからユーザーの入力メッセージを取得
    user_message = request.json['message']

    # デバッグ
    print("【処理開始】")
    print("user_message:", user_message, ":", str(len(user_message)) )

    # デバッグ
    print("【ベクトル化送信】")

    #### 質問文のベクトル化
    # 質問文をAzure OpenAIの「Ada（ベクトル化用）のデプロイモデル」に送信して、ベクトル化する
    response = openai.Embedding.create(input=user_message, engine=embedding_model_name)
    embeddings = response['data'][0]['embedding']       # ベクトル化データ

    # デバッグ
    print("【AI Search送信】")
#    print("ベクトル化文字列:", embeddings, ":", str(len(embeddings)) )

    # Azure AI Searchのクライアントオブジェクトを作成する
    search_client = SearchClient(search_service_endpoint, index_name, credential)

    # ハイブリッド検索を行う（テキスト検索とベクトル検索のハイブリッド検索）
    results = search_client.search(
        search_text=user_message,
        vectors=[Vector(
            value=embeddings,
            k=3,
            fields='vector'
        )],
        select=['title', 'chunk'],       # 取得データのフィールド名
        top=1
    )

    # Azure AI Searchの検索結果を変数に格納する
    search_result = ''
    for result in results:  
        search_result += result['chunk']
        title_result = result['title']

    # デバッグ
    print("【プロンプト生成】")
#    print("search_result:", search_result, ":", str(len(search_result)) )

    # システムプロンプトの生成
    system_prompt = f'''
    あなたは優秀なサポートAIです。ユーザーから提供される情報を日本語で読みやすい形にして回答してください。
    '''

    # ユーザプロンプトの生成
    user_prompt = f'''
    { user_message }\n参考情報：
    { search_result }
    '''

    # デバッグ
    print("system_prompt:", system_prompt, ":", str(len(system_prompt)) )
    print("user_prompt:", user_prompt, ":", str(len(user_prompt)) )

    try:

#        # ChatCompletion経由でAzure OpenAIにリクエストする ※不採用：API経由でないのでログが取れない
#        # APIのパラメータとして、システムプロンプトとユーザーのプロンプトを設定する
#        response = openai.ChatCompletion.create(
#          engine=gpt_model_name, 
#          messages=[
#                {"role": "system", "content": system_prompt},
#                {"role": "user", "content": user_prompt}
#            ]
#        )

        ## API Management経由の処理
        request_data = {
             "system_message": system_prompt
           , "user_message": user_prompt
        }

        headers={
            "Content-Type": "application/json"
         ,  "Ocp-Apim-Subscription-Key": Api_Subscription_Key
        }

        # デバッグ
        print("【API送信】")

        # Azure APIManagementI APIにリクエストを送信
        response = requests.post(
            api_url
          , json=request_data
          , headers=headers
#          , proxies=proxies  # プロキシを指定 ローカルデバッグ時
        )

        # デバッグ
        print("【API受信】")
        print("response:", response.json()["choices"][0]["message"]["content"])

        # レスポンスから生成されたテキストを成形
        generated_text = f'【{user_message}】に対する回答\n\n' + response.json()["choices"][0]["message"]["content"].replace('。', '。\n').replace('\n\n', '。\n') + f'\n\n規約ファイル：{title_result}\n'

        # デバッグ
        print("【回答成形】")
        print("generated_text:",generated_text)

        # レスポンスをWeb画面へJSON形式で返す
        return jsonify({'message': generated_text})

    except RequestException as e:
        print("error1:", response)
        # エラーメッセージを返す
        return jsonify({'message': 'エラーが発生しました、再度、入力をしてくださいね。'})

    except Exception as e:
        print("error2:", response)
        # エラーメッセージを返す
        return jsonify({'message': 'エラーが発生しました、再度、入力をしてくださいな。'})

if __name__ == '__main__':
    app.run(debug=True)
