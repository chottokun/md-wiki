---
name: utf8-environment-enforcer
description: PowerShell、コマンドプロンプト(cmd)、Python環境においてUTF-8エンコーディングを徹底し、日本語の文字化けによる「Agent execution terminated due to error」や無限ループ、ファイル破損を防止する。
metadata:
owner: development-safety
version: "1.0.0"
---

## 何をするスキルか

- PowerShellおよびコマンドプロンプト(cmd)の実行時に、標準出力をUTF-8に固定する初期化処理を自動的に挿入します。
- ファイルの読み書き（取得・保存）の全工程においてUTF-8エンコーディングを明示し、Shift-JISによる「データ破壊」を防止します。
- エージェントが日本語を正しく解釈・出力できる環境を維持し、文字化けによる無限ループや異常終了（Agent execution terminated due to error）を回避します 。


## **■ 実行手順と技術的記述 (Instructions)**

### **1\. PowerShell 実行プロトコル**

PowerShellを実行する際は、標準出力をUTF-8に固定するために冒頭に必ず以下の初期化コードを付与すること。

PowerShell

\[Console\]::OutputEncoding \=::UTF8;

**理由:** これを怠ると日本語の文字化けにより "Agent execution terminated due to error" や解析不能による無限ループがほぼ確実に発生するため。

### **2\. コマンドプロンプト (cmd) 実行プロトコル**

cmdを実行する際は、コードページをUTF-8（65001）に変更するため、冒頭に必ず以下を付与すること。

DOS

chcp 65001 \> nul &&

### **3\. ファイル操作におけるUTF-8貫徹**

PowerShellを使用してファイルを読み書き（Get-Content, Set-Content等）する際は、必ず \-Encoding UTF8 を明示すること。

* **書き込み時:** ヒアドキュメント形式で生のテキストデータとして強制書き込みを行う手法を推奨。

PowerShell

\[Console\]::OutputEncoding \=::UTF8;  
$content \= @"  
\<生のテキストデータ\>  
"@  
$content | Set-Content \-Path "\<path\>" \-Encoding UTF8

**警告:** Shift-JISでの読み込み・保存は「データ破壊」とみなし、全工程においてUTF-8を貫徹せよ。

### **4\. Python環境の強制**

Pythonスクリプトを実行する際は、暗黙のエンコーディング依存を防ぐため、UTF-8で話すように強制する（PYTHONUTF8=1 または encoding='utf-8' の明示）。
