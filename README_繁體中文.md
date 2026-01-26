# 歐盟配額爬蟲工具 v2.3

自動從歐盟委員會 TARIC 資料庫擷取鋼鐵關稅配額數據。

## 概述

本工具從歐盟 TARIC 系統爬取配額使用數據，追蹤鋼鐵進口配額。當配額耗盡時，額外進口需繳納 **25% 關稅**。

### 主要功能

- **自動數據擷取** - 從歐盟 TARIC 配額頁面擷取
- **MEPS 格式 Excel 報告** - 包含互動式篩選器
- **互動式交叉分析篩選器** - 可依配額類別和國家篩選
- **MEPS 標誌和品牌樣式** - 完整保留於輸出檔案
- **自動日期偵測** - 配額期間自動識別
- **日期資料夾** (YYYY-MM-DD) - 便於歷史追蹤
- **189 個歐盟配額** - 追蹤多種鋼鐵產品和來源國

### 計算公式（MEPS 公式）

```
配額限額 = amount + transferred_amount
剩餘餘額 = balance - awaiting_allocation
```

## 快速開始

```bash
# 安裝依賴套件
pip install -r requirements.txt

# 執行爬蟲
python run.py              # 互動模式（同時抓取歐盟和英國）
python run.py --skip-uk    # 僅抓取歐盟
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
│   ├── scraper_selenium.py        # 歐盟 Selenium 爬蟲（備份）
│   ├── uk_scraper.py              # 英國 API 爬蟲（快速版）
│   ├── uk_scraper_selenium.py     # 英國 Selenium 爬蟲（備份）
│   ├── data_processor.py          # 數據計算（MEPS 公式）
│   ├── excel_generator.py         # MEPS 報告生成器（保留篩選器）
│   └── utils.py                   # 檔案/資料夾工具函數
│
├── build/                         # 建置 EXE - 打包腳本
│   └── build_exe.py               # PyInstaller 建置腳本
│
├── dist/                          # 發布輸出
│   └── EU_Quota_Scraper/          # 可直接壓縮發布的資料夾
│
├── data/                          # 數據 - 執行時數據
│   ├── input/                     # 輸入檔案
│   │   ├── quota_urls.xlsx        # 歐盟配額追蹤清單
│   │   └── uk_quota_urls.xlsx     # 英國配額追蹤清單
│   ├── output/                    # 按日期輸出
│   │   └── YYYY-MM-DD/            # 日期資料夾
│   └── snapshots/                 # 歷史快照
│
├── templates/                     # 範本 - Excel 範本
│   └── meps_customer_template.xlsx  # MEPS 範本（含篩選器）
│
├── docs/                          # 文件 - 說明文件
│   ├── ARCHITECTURE.md            # 系統架構
│   ├── INSTRUCTIONS.md            # 英文說明
│   ├── INSTRUCTIONS_繁體中文.md    # 繁體中文說明
│   └── TODO.md                    # 功能路線圖
│
├── dev/                           # 開發工具 - 開發輔助工具
│   ├── scripts/                   # 工具腳本
│   └── analysis/                  # 分析和除錯工具
│
├── run.py                         # 便捷入口點
├── requirements.txt               # 依賴套件
├── README.md                      # 英文說明
└── README_繁體中文.md              # 本檔案
```

## 建置 EXE 發布包

建立獨立的 EXE 發布包：

```bash
python build/build_exe.py
```

發布包將建立於 `dist/EU_Quota_Scraper/` 資料夾。

**發布步驟：**
1. 執行建置腳本
2. 將 `dist/` 內的 `EU_Quota_Scraper` 資料夾壓縮成 zip
3. 將 zip 檔案發送給使用者
4. 使用者解壓縮後雙擊 `EU_Quota_Scraper.exe` 即可執行

## 技術說明

- **配額編號格式**：自動補零至 6 位數（如 `98967` → `098967`）
- **季度週期**：Q1 (1-3月), Q2 (4-6月), Q3 (7-9月), Q4 (10-12月)
- **請求間隔**：隨機延遲（歐盟：0.3-0.8秒，英國：0.2-0.5秒）
- **預估執行時間**：全部配額（歐盟+英國）約需 1-2 分鐘
- **並行處理**：5 個並行請求加速爬取

## 設定每日自動更新（Windows）

1. 開啟工作排程器 → 建立基本工作
2. 名稱：「EU Quota 爬蟲」
3. 觸發程序：每天，指定時間
4. 動作：啟動程式
   - 程式：`python`
   - 引數：`run.py --skip-uk` 或 `run.py`
   - 開始於：`C:\path\to\EU Quota`

## 文件

- [英文說明](docs/INSTRUCTIONS.md)
- [繁體中文說明](docs/INSTRUCTIONS_繁體中文.md)
- [系統架構](docs/ARCHITECTURE.md)

## 資料來源

[歐盟 TARIC 配額資料庫](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)

---

*版本 2.3 - 2026年1月（快速 HTTP 爬蟲，效能提升 10 倍）*
