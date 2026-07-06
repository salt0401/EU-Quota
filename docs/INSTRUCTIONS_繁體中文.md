# 歐盟配額爬蟲工具 - 使用說明

## 概述

本工具自動從歐盟委員會 TARIC 資料庫和英國整合線上關稅系統收集鋼鐵關稅配額數據，並生成格式化的 Excel 報告供客戶使用。

## 專案結構

```
EU Quota/
├── src/                           # 主程式 - 核心原始碼
│   ├── __init__.py                # 套件匯出
│   ├── main.py                    # 主程式入口
│   ├── config.py                  # 設定與季度工具函數
│   ├── scraper.py                 # 歐盟網頁爬蟲（直接 HTTP 請求）
│   ├── uk_scraper.py              # 英國網頁爬蟲（直接 HTTP 請求）
│   ├── data_processor.py          # 數據計算（MEPS 公式）
│   ├── excel_generator.py         # MEPS 報告生成器（保留篩選器）
│   └── utils.py                   # 檔案/資料夾工具函數
│
├── build/                         # 建置 EXE - 打包腳本
│   └── build_exe.py               # PyInstaller 建置腳本
│
├── dist/                          # 發布輸出（生成的 EXE）
│
├── data/                          # 數據 - 執行時數據
│   ├── input/                     # 輸入檔案
│   │   ├── quota_urls.xlsx        # 歐盟配額追蹤清單（283 個配額）
│   │   ├── uk_quota_urls.xlsx     # 英國配額追蹤清單（75 個配額）
│   │   └── archive/               # 舊防衛措施時期的輸入檔案（2026年7月前）
│   ├── 0702NewData/               # 2026年7月1日新法規的參考數據
│   ├── output/                    # 按日期輸出
│   │   └── YYYY-MM-DD/            # 日期資料夾
│   └── snapshots/                 # 歷史快照
│
├── templates/                     # 範本 - Excel 範本
│   ├── meps_customer_template.xlsx  # MEPS 範本（含篩選器）
│   └── archive/                   # 舊防衛措施時期的範本
│
├── docs/                          # 文件 - 說明文件
│
├── run.py                         # 便捷入口點
├── requirements.txt               # 依賴套件
└── README.md                      # 專案說明
```

## 安裝

1. 安裝 Python 3.8+ (如尚未安裝)

2. 安裝必要套件：
   ```bash
   pip install -r requirements.txt
   ```

3. 不需要 Chrome 瀏覽器 — 爬蟲使用直接 HTTP 請求

## 使用方式

### 基本使用
```bash
python run.py
```
程式會同時爬取歐盟和英國配額。

### 僅爬取歐盟（跳過英國）
```bash
python run.py --skip-uk
```
執行速度較快，適合只需要歐盟數據時使用。

### 自訂輸入/輸出
```bash
python run.py -i custom_quotas.xlsx -o custom_report.xlsx
```

### 完整選項
```bash
python run.py -i eu.xlsx -u uk.xlsx -o output.xlsx --skip-uk
```

## 輸入檔案格式

### 歐盟輸入檔案 (`data/input/quota_urls.xlsx`)

| 欄位 | 必要 | 說明 |
|------|------|------|
| Order Number | 是 | 6位數配額訂單編號（如 099801） |
| Quota Category | 是 | 產品類別名稱 |
| Country | 是 | 來源國家 |
| Current Quarter | 是 | 季度開始日期 (YYYY-MM-DD) |
| URL | 自動 | 由公式自動生成 |

### 英國輸入檔案 (`data/input/uk_quota_urls.xlsx`)

| 欄位 | 必要 | 說明 |
|------|------|------|
| Order Number | 是 | 6位數配額訂單編號（如 058600） |
| Quota Category | 是 | 產品類別名稱 |
| Country | 是 | 來源國家或配額分配名稱（如 European Union、India、Residual） |
| Current Quarter | 是 | 季度開始日期 (YYYY-MM-DD) |
| Template Quota Limit | 是 | 當季配額限額（公噸），用於計算分配比例 |
| URL | 自動 | 由公式自動生成 |

## 輸出檔案

每次執行會在 `data/output/YYYY-MM-DD/` 建立日期資料夾：

1. **eu_quota_raw_YYYYMMDD.xlsx**
   - 完整歐盟爬取數據
   - 供內部分析使用

2. **uk_quota_raw_YYYYMMDD.xlsx**
   - 完整英國爬取數據
   - 供內部分析使用

3. **MEPS_Quota_Update_YYYYMMDD.xlsx**
   - 格式化的客戶報告
   - **互動式交叉分析篩選器**（可依配額類別和國家篩選）
   - 保留 MEPS 標誌和樣式
   - 包含說明頁、歐盟數據表和英國數據表
   - 可直接交付客戶

## 數據計算

系統使用以下公式（與 MEPS 範本一致）：

| 欄位 | 公式 |
|------|------|
| 配額限額 (Quota Limit) | amount + transferred_amount |
| 剩餘餘額 (Balance Remaining) | balance - awaiting_allocation |
| 已分配配額 (Quota Allocated) | 配額限額 - 剩餘餘額 |
| 分配百分比 (% Allocated) | (已分配配額 / 配額限額) x 100 |

## 建置 EXE 發布包

建立獨立的 EXE 發布包：

```bash
python build/build_exe.py
```

發布包將建立於 `dist/` 資料夾。

## 每季維護

每個新季度開始時（1月1日、4月1日、7月1日、10月1日）：

1. 更新兩個輸入檔案（`data/input/quota_urls.xlsx` 和
   `data/input/uk_quota_urls.xlsx`）中的 `Current Quarter` 欄位為新季度開始日期
2. 更新 `data/input/uk_quota_urls.xlsx` 中的 `Template Quota Limit` 欄位為
   該季度的配額噸數，數據來源為 `data/0702NewData/uk_quotas.csv`
   （`q1_jul_sep_t` 至 `q4_apr_jun_t` 欄位）
3. 僅在 HMRC 變更訂單編號時，才需更新 `src/uk_scraper.py` 中的
   `UK_QUOTA_ORDER_NUMBERS` 字典

注意：歐盟執行條例 (EU) 2026/1457 定義的配額適用期間為 2026年7月1日至
12月31日；預計 2027年1月將發布更新條例，屆時可能需要更新
`data/input/quota_urls.xlsx`。

### 2026年7月1日起的英國訂單編號

舊的鋼鐵防衛措施（058001 系列訂單編號）已於 2026年6月30日終止。
自 2026年7月1日起，英國措施改依《Taxation (Cross-Border Trade) Act 2018》
實施（DBT 公告「UK's steel trade measure from 1 July 2026」），並採用
新的編號方案：

| 訂單編號 | 涵蓋範圍 |
|----------|----------|
| 058600-058671 | 72 個配額，涵蓋 20 個類別（DBT 公告 Table 4） |
| 058673 | 類別 1 授權用途 (authorised-use) - 歐盟（每季 238,380 公噸） |
| 058674 | 類別 1 授權用途 (authorised-use) - 印度（每季 238,380 公噸） |
| 058675 | 類別 1 授權用途 (authorised-use) - Residual（每季 119,190 公噸） |

三個授權用途配額僅公布於 UK Integrated Online Tariff 網站，未列入 DBT 公告。
未用完的配額可轉移至下一季度，但不可轉入下一個配額年度（7月1日至隔年6月30日）。
烏克蘭原產鋼鐵豁免。

## 排程設定（Windows 工作排程器）

1. 開啟工作排程器 → 建立基本工作
2. 名稱：「EU Quota 爬蟲」
3. 觸發程序：每天，指定時間
4. 動作：啟動程式
   - 程式：`python`
   - 引數：`run.py` 或 `run.py --skip-uk`
   - 開始於：`C:\path\to\EU Quota`

## 疑難排解

### Chrome 驅動程式問題（歷史備註）
爬蟲使用直接 HTTP 請求，不需要 Chrome。若
驅動程式有問題：
```bash
pip install --upgrade webdriver-manager
```

### 數據缺失
檢查：
- 訂單編號格式是否正確（6位數）
- 季度開始日期是否有效
- 歐盟 TARIC 網站是否可存取
- 英國關稅網站是否可存取

### 執行緩慢
- 歐盟 283 個配額、英國 75 個配額 — 完整執行約需 1-2 分鐘
- 每次請求之間有隨機短暫延遲，以避免速率限制

### 英國訂單編號無效
如果某個英國訂單編號返回「NO DATA」：
1. 在 UK Integrated Online Tariff 網站手動檢查
2. 查閱 DBT 公告「UK's steel trade measure from 1 July 2026」
3. 更新 `data/input/uk_quota_urls.xlsx` 中的訂單編號，並同步更新
   `src/uk_scraper.py` 中的 `UK_QUOTA_ORDER_NUMBERS` 字典

## 技術支援

如有問題或疑問：
- 查看 `data/output/` 資料夾中的日誌
- 檢視控制台輸出的錯誤訊息
- 聯繫開發團隊

---

*版本 2.6 - 2026年7月（歐盟與英國新鋼鐵配額制度，2026年7月1日生效）*
