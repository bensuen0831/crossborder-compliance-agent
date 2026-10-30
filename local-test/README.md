# Stage1 本機隔離測試套件

下載同目錄 `Stage1_Local_Test_Online_20261030.zip`，解壓縮後先讀 `START_HERE.md`。

套件ID：stage1-local-20261030-1。固定產品源碼：3d322e864a6c98c34d42657289e421c77f6c9ed1。
本delivery branch只交付本機啟動器與安全、脫敏的測試證據，不是新的產品baseline。PR29/30保持Draft，沒有merge、tag或Release。

ZIP包含完整固定源碼bundle及本機啟動器，不需GitHub登入來取得源碼；首次setup仍需連網下載固定hash的Python／Node／S3依賴、npm lock及固定Docker服務映像。
`launcher`提供與ZIP相同的可審查啟動器，依賴版本、URLs、size及SHA256在DOWNLOADS／CHECKSUMS記錄。這些旁列檔案供審查，請從ZIP安裝，而非單獨執行旁列launcher。

已在新的Linux amd64 venv／專用DB／S3實測登入、blank Project、reload、資料保留stop/start、越權403；Windows WSL2及Mac VM只提供指引，尚未實體主機驗證。
真實法規處理／即時模型／Gold／法律接受仍受原安全及F1閘門約束；沒有出廠帳號或假法律結果。詳見START_HERE及verification。
