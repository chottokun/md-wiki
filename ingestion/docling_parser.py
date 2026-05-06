import logging
from pathlib import Path
from typing import Optional
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorDevice

# ロギング設定
logger = logging.getLogger(__name__)

class DoclingParser:
    """
    Docling (v2) を使用してPDF、画像、Markdown等の文書を高精度にパースし、
    クリーンなMarkdown形式へ変換するプロセッサ。
    
    特徴:
    - 12GB VRAM等のリソース制約を考慮し、パース処理をCPUに強制（LLM推論へVRAMを優先）。
    - 各フォーマット（特にPDF）に対する詳細なパイプラインオプション管理。
    """
    
    def __init__(self, output_dir: str = "_staged"):
        """
        DoclingParserを初期化する。
        
        Args:
            output_dir (str): 変換後のMarkdownを一時保存するディレクトリ。
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 変換パイプラインの設定
        # VRAM節約と互換性のため、アクセラレータとしてCPUを指定
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options.device = AcceleratorDevice.CPU
        
        self.converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF, 
                InputFormat.IMAGE, 
                InputFormat.MD,
                InputFormat.DOCX,
                InputFormat.PPTX,
                InputFormat.HTML
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    def convert(self, file_path: str) -> Optional[Path]:
        """
        指定されたファイルを読み込み、Markdownへ変換して出力ディレクトリに保存する。
        
        Args:
            file_path (str): 変換対象のソースファイルへのパス。
            
        Returns:
            Optional[Path]: 変換後のMarkdownファイルのパス。失敗時はNone。
        """
        input_path = Path(file_path)
        if not input_path.exists():
            logger.error(f"パース対象のファイルが見つかりません: {file_path}")
            return None

        logger.info(f"{input_path.name} をMarkdownに変換中...")
        
        try:
            # パース実行
            result = self.converter.convert(input_path)
            
            # Markdownテキストとしてエクスポート
            md_content = result.document.export_to_markdown()
            
            # 出力ファイル名の生成（元のファイル名 + .md）
            output_path = self.output_dir / (input_path.stem + ".md")
            
            # UTF-8で保存
            output_path.write_text(md_content, encoding="utf-8")
            
            logger.info(f"変換成功: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"{file_path} の変換中にエラーが発生しました: {str(e)}")
            return None
