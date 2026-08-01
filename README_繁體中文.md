# 歐盟配額爬蟲工具 v2.6

自動從歐盟委員會 TARIC 資料庫與英國整合線上關稅系統（UK Integrated Online Tariff）擷取鋼鐵關稅配額數據。

## 概述

本工具從歐盟 TARIC 系統爬取配額使用數據，追蹤鋼鐵進口配額。當配額耗盡時，額外進口需繳納 **50% 關稅**（歐盟法規 (EU) 2026/1384，自 2026 年 7 月 1 日生效）。英國配額則依據英國鋼鐵貿易措施（steel trade measure，同樣自 2026 年 7 月 1 日生效，配額外關稅亦為 50%），從英國整合線上關稅系統追蹤。

### 主要功能

- **自動數據擷取** - 從歐盟 TARIC 配額頁面擷取
- **MEPS 格式 Excel 報告** - 包含互動式篩選器
- **互動式交叉分析篩選器** - 可依配額類別和國家篩選
- **MEPS 標誌和品牌樣式** - 完整保留於輸出檔案
- **自動日期偵測** - 配額期間自動識別
- **日期資料夾** (YYYY-MM-DD) - 便於歷史追蹤
- **每日無人值守執行** - 於 MEPS 公司伺服器執行，並將結果發布回 GitHub
- **283 個歐盟配額與 75 個英國配額** - 追蹤多種鋼鐵產品和來源國（新制度自 2026 年 7 月 1 日生效）

### 計算公式（MEPS 公式）

```
配額限額 = amount + transferred_amount
剩餘餘額 = balance - awaiting_allocation
```

## 每日自動更新（GitHub Actions）

自 2026 年 7 月起，爬蟲每天早上（05:30 UTC）在 GitHub Actions 上自動執行，無需任何人手動操作：

1. GitHub 伺服器自動爬取所有歐盟與英國配額並產生報告（`.github/workflows/daily-quota-update.yml`）。
2. 結果發布到兩個位置：
   - 提交到 `data/published/`：`quota_history_<年份>.csv`（每個配額每天一列，每個日曆年度一個檔案，資料分析用資料集）與 `metadata.json`（執行摘要與檔案清單）
   - 上傳到滾動式 **latest-data** release：`MEPS_Quota_Update_latest.xlsx`（最新客戶報告）與 `Quota_History_<年份>.xlsx`（格式化歷史活頁簿，每年一個）— 不進入 git，避免每日活頁簿檔案使儲存庫不斷膨脹
3. 同事執行 **`MEPS_Quota_Downloader.exe`**（單一小檔案，由 `download.py` 建置），透過公開 URL 下載上述檔案。儲存庫必須保持**公開**，如此便無需任何 token 或登入。程式會**自動更新**：啟動時比對 release 上的版本標記，若 CI 已發布新版本（`download.py` 變更時自動重建）便會自我替換 — 因此只需要發送一次。

手動觸發：GitHub → Actions → 「Daily quota update」→ Run workflow。
歷史資料每天累積，可直接用 `quota_history_<年份>.csv` / `Quota_History_<年份>.xlsx`（每年一個檔案，作為長期運行的專案設計）分析配額的每日變化。

## 快速開始

```bash
# 安裝依賴套件
pip install -r requirements.txt

# 執行爬蟲
python run.py              # 互動模式（同時抓取歐盟和英國）
python run.py --skip-uk    # 僅抓取歐盟
python run.py --publish    # 爬取 + 更新 data/published/（每日 CI 執行的動作）

# 下載最新發布的資料（同事的 EXE 所做的事）
python download.py
```

## 輸出檔案

檔案按日期組織於 `data/output/YYYY-MM-DD/`：

| 檔案 | 說明 |
|------|------|
| `eu_quota_raw_YYYYMMDD.xlsx` | 完整歐盟爬取數據 |
| `uk_quota_raw_YYYYMMDD.xlsx` | 英國配額數據 |
| `MEPS_Quota_Update_YYYYMMDD.xlsx` | 客戶報告（含交叉分析篩選器） |

快照儲存於 `data/snapshots/` 供歷史分析。

### 客戶報告欄位

| 欄位 | 說明 |
|------|------|
| Quota Category | 鋼鐵產品類別 |
| Country | 來源國家 |
| Quota Limit (Tonnes) | 可用配額總量 |
| Quota Allocated (Tonnes) | 已使用量 |
| % Quota Allocated | 使用百分比 |
| Balance Remaining (Tonnes) | 剩餘配額 |
| % Balance Remaining | 剩餘百分比 |

## 專案結構

```
EU Quota/
├── src/                           # 主程式 - 核心原始碼
│   ├── __init__.py                # 套件匯出
│   ├── main.py                    # 主程式入口
│   ├── config.py                  # 設定與季度工具函數
│   ├── scraper.py                 # 歐盟 HTTP 爬蟲（快速版）
│   ├── uk_scraper.py              # 英國 API 爬蟲（快速版）
│   ├── data_processor.py          # 數據計算（MEPS 公式）
│   ├── excel_generator.py         # MEPS 報告生成器（保留篩選器）
│   ├── publisher.py               # 寫入 data/published/（歷史資料與 metadata）
│   └── utils.py                   # 檔案/資料夾工具函數
│
├── tools/                         # 伺服器維運 - 僅用於公司伺服器部署
│   ├── server-daily-task.ps1      # 工作排程器進入點（見 docs/SERVER_DEPLOYMENT.md）
│   ├── publish_release_assets.py  # 上傳活頁簿至 GitHub release
│   └── git-askpass.cmd            # 安全地將推送權杖交給 git
│
├── build/                         # 建置 EXE - 打包腳本
│   └── build_exe.py               # PyInstaller 建置腳本
│
├── dist/                          # 發布輸出
│   └── EU_Quota_Scraper/          # 可直接壓縮發布的資料夾
│
├── data/                          # 數據 - 執行時數據
│   ├── input/                     # 輸入檔案
│   │   ├── quota_urls.xlsx        # 歐盟配額追蹤清單（283 個配額）
│   │   ├── uk_quota_urls.xlsx     # 英國配額追蹤清單（75 個配額）
│   │   └── archive/               # 舊防衛措施輸入檔（2026 年 7 月前）
│   ├── 0702NewData/               # 2026 年 7 月新制度參考資料
│   ├── output/                    # 按日期輸出
│   │   └── YYYY-MM-DD/            # 日期資料夾
│   ├── snapshots/                 # 歷史快照
│   └── logs/                      # 每日伺服器執行日誌
│
├── templates/                     # 範本 - Excel 範本
│   ├── meps_customer_template.xlsx  # MEPS 範本（含篩選器）
│   └── archive/                   # 舊防衛措施範本（2026 年 7 月前）
│
├── docs/                          # 文件 - 說明文件
│   ├── ARCHITECTURE.md            # 系統架構
│   ├── INSTRUCTIONS.md            # 英文說明
│   ├── INSTRUCTIONS_繁體中文.md    # 繁體中文說明
│   └── TODO.md                    # 功能路線圖
│
├── beta/                          # 實驗性 - 預測功能（與 src/ 完全隔離）
│   ├── forecasting/               # Prophet 資料載入器 + Phase 2 骨架
│   └── tests/                     # beta 專用單元測試
│
├── tests/                         # 主管線單元測試
│
├── run.py                         # 便捷入口點
├── download.py                    # 同事使用的下載器（僅標準函式庫）
├── requirements.txt               # 依賴套件（本機開發，含 Selenium 備援）
├── requirements-ci.txt            # 每日自動執行所用的鎖定版本
├── README.md                      # 英文說明
└── README_繁體中文.md              # 本檔案
```

## 建置 EXE 發布包

可建置兩個執行檔：

```bash
python build/build_downloader_exe.py   # MEPS_Quota_Downloader.exe（同事使用的下載器）
python build/build_exe.py              # EU_Quota_Scraper.exe（完整本機爬蟲，選用）
```

**發布下載器（建議做法）：** 同事只需從 [latest-data release](https://github.com/salt0401/EU-Quota/releases/tag/latest-data) 取得單一檔案一次（或由你傳送給他們）。雙擊即可將最新發布的資料下載到 EXE 旁的 `data/output/YYYY-MM-DD/` — 不會在他們的機器上執行爬蟲，因此數秒即完成。此 EXE 會**自我更新**：啟動時比對 release 上的 `downloader_version.txt`，當 CI 發布較新版本時便自我替換（`.github/workflows/build-downloader.yml` 會在每次 `download.py` 變更時重建），因此只需散發一次。

**完整爬蟲發布包**（`dist/EU_Quota_Scraper/`）僅在必須於本機爬取（例如 GitHub 無法連線時）才需要。

## 技術說明

- **配額編號格式**：自動補零至 6 位數（如 `99801` → `099801`；歐盟配額編號為 `0994xx`-`0999xx`，英國為 `0586xx`）
- **季度週期**：Q1 (1-3月), Q2 (4-6月), Q3 (7-9月), Q4 (10-12月)；注意英國配額年度為 7 月 1 日至隔年 6 月 30 日
- **請求間隔**：隨機延遲（歐盟：0.3-0.8秒，英國：0.2-0.5秒）
- **預估執行時間**：全部配額（歐盟+英國）約需 2-3 分鐘
- **並行處理**：5 個並行請求加速爬取

## 文件

- [伺服器部署與運維手冊](docs/SERVER_DEPLOYMENT.md) — 每日排程在公司伺服器上的運作方式
- [每日更新運維手冊](docs/DAILY_UPDATE_RUNBOOK.md) — 執行失敗時的排查步驟
- [英文說明](docs/INSTRUCTIONS.md)
- [繁體中文說明](docs/INSTRUCTIONS_繁體中文.md)
- [系統架構](docs/ARCHITECTURE.md)

> **v2.10.0 已移除：** 登入觸發的自動快照功能（`daily_snapshot.py`、
> `src/snapshot_scheduler.py`、`setup_scheduler.bat`、`remove_scheduler.bat`）。
> 該功能早於自動化每日發布機制，且僅在有人登入 Windows 時才會擷取快照 —
> 而無人值守的伺服器永遠不會發生登入。
> `data/published/quota_history_<YEAR>.csv` 中的每日歷史資料已完整取代它。

## 資料來源

- [歐盟 TARIC 配額資料庫](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)
- [英國整合線上關稅系統](https://www.trade-tariff.service.gov.uk/quota_search)

---

*版本 2.6 - 2026年7月（歐盟/英國新配額制度，自 2026 年 7 月 1 日生效）*
