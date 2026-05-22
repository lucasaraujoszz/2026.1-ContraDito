#!/usr/bin/env python3
"""
Script 01 - Extração de Texto dos PDFs
========================================
Extrai ementa, texto articulado e justificativa de cada proposição.

Suporta:
- PDFs digitais (texto selecionável) via pdfplumber
- PDFs escaneados (imagem) via OCR com tesseract

Entrada: proposicoes/pl_001.pdf até pl_005.pdf
Saída: proposicoes/textos/pl_001.txt até pl_005.txt

Como rodar:
    python 01_extrair_texto.py

Estrutura do texto extraído:
    EMENTA: [resumo de 1 linha]
    
    TEXTO DA LEI:
    [todos os artigos]
    
    JUSTIFICATIVA:
    [argumentação completa]
"""

import os
import re
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from pathlib import Path

# Cores para output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def print_status(message, color=YELLOW):
    """Imprime mensagem colorida"""
    print(f"{color}{message}{RESET}")

def is_scanned_pdf(pdf_path):
    """
    Detecta se o PDF é escaneado (imagem) ou digital (texto).
    Retorna True se for escaneado.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Verifica as 2 primeiras páginas
            for page in pdf.pages[:2]:
                text = page.extract_text()
                if text and len(text.strip()) > 100:
                    # Tem texto extraível, é digital
                    return False
        # Não conseguiu extrair texto, é escaneado
        return True
    except Exception as e:
        print_status(f"Erro ao verificar tipo do PDF: {e}", RED)
        return False

def extract_text_digital(pdf_path):
    """Extrai texto de PDF digital usando pdfplumber"""
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        return text.strip()
    except Exception as e:
        print_status(f"Erro ao extrair texto digital: {e}", RED)
        return None

def extract_text_ocr(pdf_path):
    """Extrai texto de PDF escaneado usando OCR (tesseract)"""
    try:
        print_status("  → PDF escaneado detectado, usando OCR (pode demorar)...", YELLOW)
        
        # Converte PDF para imagens
        images = convert_from_path(pdf_path, dpi=300)
        
        text = ""
        for i, image in enumerate(images):
            print_status(f"    Processando página {i+1}/{len(images)}...", YELLOW)
            # OCR em português
            page_text = pytesseract.image_to_string(image, lang='por')
            text += page_text + "\n\n"
        
        return text.strip()
    except Exception as e:
        print_status(f"Erro ao extrair texto via OCR: {e}", RED)
        return None

def clean_text(text):
    """
    Remove elementos indesejados do texto:
    - Rodapés de assinatura eletrônica
    - Quebras de linha excessivas
    - Espaços múltiplos
    """
    # Remove linhas de assinatura eletrônica
    text = re.sub(r'\*CD\d+\*', '', text)
    text = re.sub(r'Assinado eletronicamente.*?CD\d+', '', text, flags=re.DOTALL)
    text = re.sub(r'Para verificar a assinatura.*?camara\.leg\.br.*', '', text)
    text = re.sub(r'PL n\.\d+/\d+\s*Apresentação:.*?Mesa', '', text)
    
    # Normaliza espaços e quebras de linha
    text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 quebras consecutivas
    text = re.sub(r' {2,}', ' ', text)  # Max 1 espaço
    text = re.sub(r'\n ', '\n', text)  # Remove espaços após quebra
    
    return text.strip()

def extract_sections(text):
    """
    Extrai as 3 seções principais:
    1. Ementa (após cabeçalho, antes de "O Congresso Nacional decreta")
    2. Texto articulado (de "O Congresso..." até "JUSTIFICAÇÃO")
    3. Justificativa (de "JUSTIFICAÇÃO" até o final, exceto assinaturas)
    """
    sections = {
        'ementa': '',
        'texto_articulado': '',
        'justificativa': ''
    }
    
    # 1. Extrai EMENTA (texto entre cabeçalho e "O Congresso Nacional decreta")
    ementa_match = re.search(
        r'PROJETO DE LEI.*?\(Da.*?\)(.*?)(?=O Congresso Nacional decreta|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if ementa_match:
        sections['ementa'] = ementa_match.group(1).strip()
    
    # 2. Extrai TEXTO ARTICULADO (de "O Congresso..." até "JUSTIFICAÇÃO")
    artigos_match = re.search(
        r'(O Congresso Nacional decreta:.*?)(?=JUSTIFICAÇÃO|JUSTIFICATIVA|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if artigos_match:
        sections['texto_articulado'] = artigos_match.group(1).strip()
    
    # 3. Extrai JUSTIFICATIVA (de "JUSTIFICAÇÃO" até assinaturas ou fim)
    justif_match = re.search(
        r'(?:JUSTIFICAÇÃO|JUSTIFICATIVA)(.*?)(?=Sala das Sessões|Diante do exposto|^\s*[A-Z\s]+\s*Deputad[oa]|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if justif_match:
        sections['justificativa'] = justif_match.group(1).strip()
    
    return sections

def format_output(sections):
    """Formata as seções extraídas no formato final"""
    output = ""
    
    if sections['ementa']:
        output += "EMENTA:\n"
        output += sections['ementa'] + "\n\n"
    
    if sections['texto_articulado']:
        output += "TEXTO DA LEI:\n"
        output += sections['texto_articulado'] + "\n\n"
    
    if sections['justificativa']:
        output += "JUSTIFICATIVA:\n"
        output += sections['justificativa'] + "\n"
    
    return output.strip()

def process_pdf(pdf_path, output_path):
    """
    Processa um PDF: detecta tipo, extrai texto, limpa, separa seções, salva
    """
    pdf_name = os.path.basename(pdf_path)
    print_status(f"\nProcessando: {pdf_name}", YELLOW)
    
    # 1. Detecta se é escaneado ou digital
    is_scanned = is_scanned_pdf(pdf_path)
    
    # 2. Extrai texto
    if is_scanned:
        raw_text = extract_text_ocr(pdf_path)
    else:
        print_status("  → PDF digital detectado, extraindo texto...", YELLOW)
        raw_text = extract_text_digital(pdf_path)
    
    if not raw_text:
        print_status(f"  ✗ Falha ao extrair texto de {pdf_name}", RED)
        return False
    
    # 3. Limpa o texto
    clean = clean_text(raw_text)
    
    # 4. Extrai seções
    sections = extract_sections(clean)
    
    # Verifica se conseguiu extrair ao menos uma seção
    if not any(sections.values()):
        print_status(f"  ⚠ Nenhuma seção identificada em {pdf_name}", RED)
        # Salva o texto bruto mesmo assim para debug
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(clean)
        print_status(f"  → Texto bruto salvo em {os.path.basename(output_path)}", YELLOW)
        return True
    
    # 5. Formata e salva
    formatted = format_output(sections)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(formatted)
    
    # Estatísticas
    stats = []
    if sections['ementa']:
        stats.append("ementa")
    if sections['texto_articulado']:
        stats.append("artigos")
    if sections['justificativa']:
        stats.append("justificativa")
    
    print_status(f"  ✓ Extraído: {', '.join(stats)}", GREEN)
    print_status(f"  → Salvo em: {os.path.basename(output_path)}", GREEN)
    
    return True

def main():
    print_status("="*60, YELLOW)
    print_status("  EXTRAÇÃO DE TEXTO DAS PROPOSIÇÕES", YELLOW)
    print_status("="*60, YELLOW)
    
    # Diretórios
    proposicoes_dir = Path("proposicoes")
    output_dir = Path("proposicoes/textos")
    
    # Cria diretório de saída se não existir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Lista os PDFs
    pdf_files = sorted(proposicoes_dir.glob("pl_*.pdf"))
    
    if not pdf_files:
        print_status("\n✗ Nenhum arquivo pl_*.pdf encontrado em proposicoes/", RED)
        print_status("  Certifique-se de que os PDFs estão nomeados: pl_001.pdf, pl_002.pdf, etc.\n", YELLOW)
        return
    
    print_status(f"\nEncontrados {len(pdf_files)} PDFs para processar\n", YELLOW)
    
    # Processa cada PDF
    success_count = 0
    for pdf_path in pdf_files:
        output_name = pdf_path.stem + ".txt"  # pl_001.pdf -> pl_001.txt
        output_path = output_dir / output_name
        
        if process_pdf(pdf_path, output_path):
            success_count += 1
    
    # Resumo final
    print_status("\n" + "="*60, YELLOW)
    print_status(f"  CONCLUÍDO: {success_count}/{len(pdf_files)} arquivos processados", GREEN)
    print_status("="*60, YELLOW)
    
    if success_count == len(pdf_files):
        print_status("\n✓ Todos os textos foram extraídos com sucesso!", GREEN)
        print_status(f"  Os arquivos .txt estão em: {output_dir}/\n", GREEN)
        print_status("Próximo passo: python 02_gerar_resumo.py\n", YELLOW)
    else:
        print_status(f"\n⚠ Alguns arquivos falharam. Verifique os erros acima.\n", YELLOW)

if __name__ == "__main__":
    main()