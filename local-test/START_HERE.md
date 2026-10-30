# Stage1 本機隔離測試包 — 先讀此頁

本套件讓你在自己的隔離 Linux 環境開啟業務介面。源碼固定為
`3d322e864a6c98c34d42657289e421c77f6c9ed1`（PR #30 Draft）。
套件不包含雲端帳號、API key、用戶資料、服務volume或未提交內容。

**目前可測：登入、建立空白項目、業務輸入／介面、管理入口、資料保存及權限拒絕。完整真實法律E2E尚未就緒。** 文件處理的安全閘門保持阻擋；沒有附送一個「假成功」模型、法律結果、專家Gold或預先批准的政策。模型API與真實法規須由你透過正式管理入口配置／上傳，並完成既有治理及安全要求後才可使用。

## 1. 環境與下載內容

- 實測目標：Linux amd64、CPython3.12、Git及本機Docker Engine socket。
- Windows：使用 WSL2 Ubuntu24.04 + Docker Desktop 的 WSL integration。包內提供啟動入口，**尚未在實體Windows主機驗證**。
- Mac：在Ubuntu24.04 **amd64** Linux虛擬機內執行；Intel可用x86虛擬機，Apple Silicon須支援amd64模擬的虛擬機（例如UTM），效能與相容性需另驗。**不將macOS／ARM原生列為已測支援**。
- 建議Linux環境4CPU、8GiB RAM以上（16GiB較佳）、至少40GiB可用磁碟；大型文件測試另需空間。
- 兩個版本使用相同源碼與校驗：小型「有網絡安裝版」附完整Git source bundle及本機啟動器，首次setup依固定SHA256自動下載Python wheels、官方Node24.19.0 linux-x64及SeaweedFS4.48；「已附依賴版」預先包含這些檔案。下載都經TLS、預期size及SHA256驗證，不載入雲端憑證。
- **兩版首次setup均須連網**：下載package-lock指定的npm套件，以及已固定digest的PostgreSQL17+pgvector／Redis映像；小型版另外下載上述固定版本依賴。因此不是完全離線安裝包。不需要GitHub登入或生產憑證。
- 沒有附帶已知仍待安全處置的866MB native工具映像。已有的真實image identity與掃描metadata只用於fail-closed預檢，並非本機已安裝或已重新掃描。不要手改掃描／日期來放行。

## 2. Windows 操作

1. 安裝並啟用 WSL2 Ubuntu24.04；若尚未有WSL，可由你在管理員PowerShell執行：
   `wsl --install -d Ubuntu-24.04`，依Windows要求重啟，完成Ubuntu本機使用者設定。
2. 安裝／啟動Docker Desktop，啟用 Linux containers、WSL2 backend，並在Settings → Resources → WSL Integration啟用該Ubuntu。不要將Docker daemon公開為TCP服務。
3. 在Ubuntu終端執行一次：

   ```bash
   sudo apt-get update
   sudo apt-get install -y python3.12-venv git ca-certificates
   docker --host=unix:///var/run/docker.sock info
   ```

4. 在Windows解壓縮本ZIP（建議如`C:\stage1-local`），雙擊 `OPEN_WINDOWS.cmd`。
   第一次會**複製到WSL的Linux家目錄** `~/stage1-local-20261030-1`，之後沿用，不覆蓋資料；避免NTFS權限與venv symlink問題。
5. 選`1`初始化；完成後重新開啟，選`3`建立業務帳號，自訂至少16字元密碼；再選`2`啟動。
6. 在Windows瀏覽器開 `http://127.0.0.1:15174/intake`。此時才是**你的本機**網址。依賴Windows／WSL localhost forwarding已正常工作；若未開啟，先用WSL內的`curl`核對服務，再處理WSL網路設定，不改綁0.0.0.0。

如果WSL distribution名稱不是Ubuntu-24.04，可在cmd先執行
`set STAGE1_WSL_DISTRO=你的實際distribution名稱`，但其中必須具備上述Linux/Python平台。

## 3. Linux／Linux虛擬機操作

解壓縮到Linux檔案系統。先安裝Git、Python3.12-venv及已啟動的本機Docker，然後：

```bash
cd stage1-local
bash START.sh setup
bash START.sh account --username tester --role business
bash START.sh start
```

只在你選擇`setup`時初始化套件專用資料庫並升級到現有0024；不接入或遷移你其他資料庫。
Python虛擬環境在`.runtime/venv`，固定Node在`.runtime/node`，沒有改寫系統Python/Node。

開啟同一Linux主機／VM內瀏覽器：

```text
http://127.0.0.1:15174/intake
```

若要從Mac主機瀏覽器讀取Linux VM，可使用你已有SSH登入權限的私人轉發：

```bash
ssh -N -L 15174:127.0.0.1:15174 -L 19400:127.0.0.1:19400 你的使用者@你的VM地址
```

再在Mac開同一loopback網址。這是你自己的VM地址，不是Codex雲端地址；本包不建立公開tunnel，也不自動建立SSH服務。19400是本機檔案儲存端點，並不代表安全閘門已解除。

## 4. 帳號、角色與介面

帳號都由你在本機設定，沒有通用預設密碼：

```bash
bash START.sh account --username kb-author --role knowledge-author
bash START.sh account --username config-reviewer --role configuration-reviewer
bash START.sh account --username config-publisher --role configuration-publisher
bash START.sh account --username workflow-reviewer --role workflow-reviewer
```

技術角色配置**不等於**正式任命法律專家、安全Reviewer或取得法律批准。不得用同一人自批來冒充獨立審查。

- 業務：`/intake`；人工審核：`/reviews`。
- 管理：`/admin?admin_resource=knowledge-management`。
- 模型：`/admin?admin_resource=models`。
- F1：`/admin?admin_resource=regulatory-acceptance`。
- 健康：`http://127.0.0.1:18011/health/live`。

新Project如需exact project grant，先由UI建立，記下實際UUID，再由本機操作者：

```bash
bash START.sh grant-project --username tester --project-id 實際ProjectUUID
```

帳號更新／授權後重新登入。不要提供`system`、萬用tenant或用戶自行指定actor authority。

## 5. 停止、重啟與保留資料

```bash
bash START.sh status
bash START.sh stop
bash START.sh start
```

`.state`保存本機私有帳號、secret-store、文件及S3資料；PostgreSQL／Redis保存於套件專用Docker volumes。
`stop`會等待檔案儲存服務正常結束（最長40秒，超時保留資料與owner記錄，不強制殺死）；只停止已核對ownership的本套件服務，**不刪除資料、volume或做reset**。重啟後需重新登入。
不要重新解壓縮覆蓋既有`.state`，不要執行`docker volume prune`、`down -v`或隨意刪除資料夾。
若要另起一份測試環境，先停本份，再解壓縮至新資料夾；不把「Reset」當作清除歷史Snapshot。

服務只綁loopback：前端15174、API18011、PostgreSQL26544、Redis26384、S3 19400。
遇到port占用會拒絕替換，不會停別人的程式。不要同時啟動兩份。

## 6. 現有安全／E2E限制

- libxml2已有官方支援修補的工具映像記錄，但新版仍有32筆CVSS>=7套件findings／21個CVE；部分Tesseract修補需要既有ESM授權，其餘待支援修復／正式Reviewer處置。
- 歷史scan不會在本機重設時間或當作新掃描。本包沒有關閉scan、添加browser retry或偽造乾淨scanner，真實文件native processing保持BLOCKED。
- 業務需求附件在固定源碼中僅接入bounded TXT（<=1MiB）；業務DOCX處理仍需canonical owner後續整合，不能因本機打包宣稱已提供。法規管理保留六格式檔案選擇介面；成功處理／發布真實法規還需要安全條件及正式上傳政策。出現阻擋訊息是預期的fail-closed，不是上傳已成功。
- ChatGPT訂閱不提供本應用的後端API憑證。模型key只在本機正式Secret Store設定；不得貼聊天或提交Git。
- 必須另備經授權真實原檔、來源／版本／有效性核驗、獨立專家Gold及身份／日期／版本／批准與評估標準，才能進行F1法律準確性驗收。
- 未執行的真實模型／法律驗收保持NOT_EXECUTED；正式安全接受Pending，Production Deployment／UAT未接受，Stage2未開始。

## 7. 排錯與校驗

`bash START.sh verify`會核對已附payload SHA256；小型版尚未下載的依賴會清楚列為待下載，setup取得後再核對完整payload。不要修改assets以繞過預檢。
私有診斷位於`.state/logs`；不要直接把整個`.state`、帳號檔、model-secrets或logs上傳。
報告問題時只提供：套件ID、source SHA、作業系統、執行步驟、錯誤代碼及脫敏截圖。

若venv初始化失敗，確認Ubuntu24.04的`python3.12-venv`完整可用；不刪除DB來處理Python問題。
若前端安裝失敗，查看私有frontend-install.log並確認npm registry連線與TLS；不要關閉TLS或修改package-lock。
Docker socket權限需由你依組織政策設定；docker group屬高權限，不應給未知帳號。
本包啟動器沒有要求公開Docker socket、privileged app container或新付費服務。
