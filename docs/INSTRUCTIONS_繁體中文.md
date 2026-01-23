# 歐盟配額爬蟲工具 - 使用說明

## 概述

本工具自動從歐盟委員會 TARIC 資料庫收集鋼鐵關稅配額數據，並生成格式化的 Excel 報告供客戶使用。

## 專案結構

```
EU Quota/
├── src/                        # 原始碼模組
│   ├── config.py              # 設定與季度工具函數
│   ├── scraper.py             # 使用 Selenium 的網頁爬蟲
│   ├── data_processor.py      # 數據清理與計算
│   ├── excel_generator.py     # MEPS 報告生成器
│   └── utils.py               # 檔案/資料夾工具函數
├── data/
│   ├── input/                 # 輸入檔案
│   │   └── quota_urls.xlsx    # 要爬取的配額清單
│   ├── output/                # 按日期分類的輸出檔案
│   │   └── YYYY-MM-DD/        # 日期資料夾
│   │       ├── eu_quota_raw_*.xlsx
│   │       └── MEPS_EU_Quota_Update_*.xlsx
│   └── snapshots/             # 歷史快照
├── templates/                 # 參考範本
├── docs/                      # 文件
├── scripts/                   # 開發腳本
└── main.py                    # 主程式入口
```

## 安裝

1. 安裝 Python 3.8+ (如尚未安裝)

2. 安裝必要套件：
   ```bash
   pip install -r requirements.txt
   ```

3. 必須安裝 Chrome 瀏覽器 (供 Selenium 使用)

## 使用方式

### 互動模式
```bash
python main.py
```
程式會在開始前提示確認。

### 自動模式（適用於排程）
```bash
python main.py --auto
```
無需確認直接執行 - 適合 Windows 工作排程器。

### 自訂輸入/輸出
```bash
python main.py -i custom_quotas.xlsx -o custom_report.xlsx
```

## 輸入檔案格式

輸入檔案（`data/input/quota_urls.xlsx`）必須包含：

| 欄位 | 必要 | 說明 |
|------|------|------|
| Order Number | 是 | 6位數配額訂單編號 |
| Quota Category | 否 | 產品類別名稱 |
| Country | 否 | 來源國家 |
| Current Quarter | 否 | 季度開始日期 (YYYY-MM-DD) |

## 輸出檔案

每次執行會在 `data/output/YYYY-MM-DD/` 建立日期資料夾：

1. **eu_quota_raw_YYYYMMDD.xlsx**
   - 完整爬取數據，包含所有欄位
   - 供內部分析使用

2. **MEPS_EU_Quota_Update_YYYYMMDD.xlsx**
   - 格式化的客戶報告
   - 包含說明頁和數據表格
   - 可直接交付客戶

## 數據計算

系統使用以下公式（與 MEPS 範本一致）：

| 欄位 | 公式 |
|------|------|
| 配額限額 (Quota Limit) | amount + transferred_amount |
| 剩餘餘額 (Balance Remaining) | balance - awaiting_allocation |
| 已分配配額 (Quota Allocated) | 配額限額 - 剩餘餘額 |
| 分配百分比 (% Allocated) | (已分配配額 / 配額限額) x 100 |

## 自動填入欄位

以下欄位從爬取數據自動偵測：

- **當前配額期間**：從 validity_period 欄位提取
- **最新可用數據**：使用爬取日期

## 手動步驟

執行爬蟲後：

1. 檢視生成的 MEPS 報告
2. 如有需要，添加政策變更備註
3. 驗證數據準確性
4. 交付給客戶

## 排程設定（未來功能）

要設定每日自動爬取，使用 Windows 工作排程器：

1. 建立新工作
2. 設定觸發程序（例如：每天早上 6:00）
3. 動作：啟動程式
   - 程式：`python`
   - 引數：`main.py --auto`
   - 開始於：`C:\path\to\EU Quota`

## 疑難排解

### Chrome 驅動程式問題
程式會自動下載正確的 Chrome 驅動程式。如有問題：
```bash
pip install --upgrade webdriver-manager
```

### 數據缺失
檢查：
- 訂單編號格式是否正確（6位數）
- 季度開始日期是否有效
- 歐盟 TARIC 網站是否可存取

### 執行緩慢
- 正常執行時間：189 個配額約需 15-20 分鐘
- 每次請求間隔 1 秒以避免速率限制

## 技術支援

如有問題或疑問：
- 查看 `data/output/` 資料夾中的日誌
- 檢視控制台輸出的錯誤訊息
- 聯繫開發團隊

---

*版本 2.0 - 2026年1月*
