#!/usr/bin/env python3
"""
=============================================================
INTELLIGENT CLINICAL PDF PROCESSOR WITH AUTO-DETECTION
Version 4.0 - Multi-Document Type Support
=============================================================
Automatically detects and processes:
- Clinical Case Reports
- Medical Textbooks
- Clinical Guidelines
- Discharge Summaries
- Research Articles
- Lab Reports
=============================================================
"""

import sys
import os
import platform
from pathlib import Path
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Union
import re
import json
import hashlib
import subprocess
from datetime import datetime
from collections import defaultdict

# Check Python version
if sys.version_info < (3, 7):
    print("❌ Python 3.7+ required")
    sys.exit(1)

print("🚀 Intelligent Clinical PDF Processor\n")
print("📦 Installing/checking packages...\n")

# Install required packages
def install_package(package):
    try:
        __import__(package.split('==')[0].replace('-', '_'))
        return True
    except ImportError:
        print(f"   Installing {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
            return True
        except:
            return False

packages = ["PyMuPDF", "tqdm", "colorama"]
for pkg in packages:
    if not install_package(pkg):
        print(f"❌ Failed to install {pkg}")
        sys.exit(1)

print("✅ Packages ready!\n")

import fitz  # PyMuPDF
from tqdm import tqdm
from colorama import init, Fore, Style

# Initialize colorama
init()

# Try GUI imports
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    import threading
    GUI_AVAILABLE = True
except:
    GUI_AVAILABLE = False
    print("⚠️ GUI not available, using command line mode\n")


class DocumentType(Enum):
    """Document type classifications"""
    CASE_REPORT = "case_report"
    TEXTBOOK = "textbook"
    CLINICAL_GUIDELINE = "guideline"
    DISCHARGE_SUMMARY = "discharge_summary"
    RESEARCH_ARTICLE = "research_article"
    LAB_REPORT = "lab_report"
    RADIOLOGY_REPORT = "radiology_report"
    UNKNOWN = "unknown"


class IntelligentClinicalExtractor:
    """
    Intelligent extractor that auto-detects document type
    and applies appropriate extraction strategy
    """
    
    def __init__(self, output_base_dir: str = None):
        # Setup output directory
        if output_base_dir:
            self.output_dir = output_base_dir
        else:
            desktop = Path.home() / "Desktop"
            self.output_dir = str(desktop / f"IntelligentPDFOutput_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"📁 Output: {self.output_dir}\n")
        
        # Document type indicators
        self.doc_type_patterns = {
            DocumentType.CASE_REPORT: {
                'keywords': ['case report', 'case presentation', 'we report', 'we present', 
                            'a case of', 'rare case', 'unusual presentation'],
                'patterns': [
                    r'[Aa]\s+\d{1,3}[\s\-]*year[\s\-]*old',
                    r'presented\s+with',
                    r'was\s+diagnosed\s+with'
                ],
                'max_pages': 15,
                'weight': 1.0
            },
            DocumentType.TEXTBOOK: {
                'keywords': ['chapter', 'section', 'learning objectives', 'review questions',
                            'summary', 'key points', 'bibliography', 'references', 'edition'],
                'patterns': [
                    r'Chapter\s+\d+',
                    r'Section\s+\d+\.\d+',
                    r'Figure\s+\d+\.\d+'
                ],
                'min_pages': 30,
                'weight': 0.8
            },
            DocumentType.CLINICAL_GUIDELINE: {
                'keywords': ['guideline', 'recommendation', 'protocol', 'consensus', 
                            'algorithm', 'evidence level', 'grade', 'standard of care'],
                'patterns': [
                    r'Level\s+[A-C]\s+evidence',
                    r'Grade\s+\d+[A-C]?\s+recommendation',
                    r'should\s+be\s+(?:considered|performed|avoided)'
                ],
                'weight': 0.9
            },
            DocumentType.DISCHARGE_SUMMARY: {
                'keywords': ['discharge', 'admission', 'hospital course', 'discharge diagnosis',
                            'discharge medications', 'follow up', 'disposition'],
                'patterns': [
                    r'Date\s+of\s+Admission',
                    r'Date\s+of\s+Discharge',
                    r'Discharge\s+Diagnosis'
                ],
                'max_pages': 10,
                'weight': 0.95
            },
            DocumentType.RESEARCH_ARTICLE: {
                'keywords': ['abstract', 'introduction', 'methods', 'results', 'discussion',
                            'conclusion', 'participants', 'study design', 'statistical analysis'],
                'patterns': [
                    r'[Pp]\s*[<=]\s*0\.\d+',
                    r'[Nn]\s*=\s*\d+',
                    r'95%\s+CI'
                ],
                'weight': 0.85
            },
            DocumentType.LAB_REPORT: {
                'keywords': ['laboratory', 'specimen', 'reference range', 'abnormal',
                            'test name', 'result', 'units', 'collected'],
                'patterns': [
                    r'\d+\.\d+\s*-\s*\d+\.\d+',  # ranges
                    r'[HL]\s*$',  # High/Low markers
                    r'mg/dL|mmol/L|IU/mL'
                ],
                'max_pages': 5,
                'weight': 0.9
            },
            DocumentType.RADIOLOGY_REPORT: {
                'keywords': ['impression', 'findings', 'technique', 'comparison', 
                            'indication', 'ct', 'mri', 'xray', 'ultrasound'],
                'patterns': [
                    r'IMPRESSION:',
                    r'FINDINGS:',
                    r'TECHNIQUE:'
                ],
                'max_pages': 5,
                'weight': 0.95
            }
        }
        
        self.processed_files = []
        self.failed_files = []
    
    def classify_document(self, text: str, page_count: int) -> Tuple[DocumentType, float]:
        """
        Classify document type using intelligent heuristics
        Returns: (DocumentType, confidence_score)
        """
        scores = defaultdict(float)
        first_3k_chars = text[:3000].lower()
        
        for doc_type, indicators in self.doc_type_patterns.items():
            score = 0.0
            matches = 0
            
            # Check keywords
            for keyword in indicators['keywords']:
                if keyword in first_3k_chars:
                    score += 1
                    matches += 1
            
            # Check regex patterns
            for pattern in indicators['patterns']:
                if re.search(pattern, first_3k_chars, re.IGNORECASE):
                    score += 1.5  # Patterns weighted higher
                    matches += 1
            
            # Apply page count constraints
            if 'min_pages' in indicators and page_count < indicators['min_pages']:
                score *= 0.3
            if 'max_pages' in indicators and page_count > indicators['max_pages']:
                score *= 0.5
            
            # Normalize and apply weight
            if matches > 0:
                score = (score / max(len(indicators['keywords']) + len(indicators['patterns']), 1))
                score *= indicators['weight']
                scores[doc_type] = score
        
        # Get best match
        if scores:
            best_type = max(scores.items(), key=lambda x: x[1])
            if best_type[1] > 0.2:  # Minimum confidence threshold
                return best_type[0], best_type[1]
        
        # Fallback classification based on structure
        if page_count > 50:
            return DocumentType.TEXTBOOK, 0.6
        elif 'patient' in first_3k_chars and 'diagnosis' in first_3k_chars:
            return DocumentType.CASE_REPORT, 0.4
        
        return DocumentType.UNKNOWN, 0.0
    
    def extract_case_report_data(self, text: str) -> Dict[str, Any]:
        """Extract data specific to case reports"""
        data = {
            'document_type': 'case_report',
            'patient': {},
            'timeline': {},
            'clinical_findings': {},
            'diagnostics': {},
            'interventions': {},
            'outcomes': {}
        }
        
        # Patient demographics
        age_match = re.search(r'\b(\d{1,3})[\s\-]*year[\s\-]*old', text, re.IGNORECASE)
        if age_match:
            data['patient']['age'] = int(age_match.group(1))
        
        gender_match = re.search(r'\b(male|female|man|woman)\b', text, re.IGNORECASE)
        if gender_match:
            data['patient']['gender'] = gender_match.group(1).lower()
        
        # Chief complaint
        complaint_match = re.search(r'presented\s+with\s+([^\.]{10,100})', text, re.IGNORECASE)
        if complaint_match:
            data['clinical_findings']['chief_complaint'] = complaint_match.group(1).strip()
        
        # Timeline extraction
        timeline_patterns = [
            (r'(\d+)\s*days?\s+(?:prior|before|ago)', 'onset_days'),
            (r'day\s+(\d+)\s+of\s+(?:admission|illness)', 'illness_day'),
            (r'(?:after|following)\s+(\d+)\s*days?', 'duration_days')
        ]
        
        for pattern, field in timeline_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['timeline'][field] = int(match.group(1))
        
        # Lab values with trends
        self._extract_lab_values(text, data)
        
        # Diagnosis
        dx_patterns = [
            r'(?:final\s+)?diagnosis\s*:?\s*([^\.]+)',
            r'diagnosed\s+with\s+([^\.]+)',
            r'consistent\s+with\s+([^\.]+)'
        ]
        
        for pattern in dx_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['diagnostics']['primary_diagnosis'] = match.group(1).strip()
                break
        
        # Treatment
        self._extract_medications(text, data)
        
        # Outcome
        outcome_patterns = [
            r'(recovered|died|discharged|transferred)',
            r'(complete\s+recovery|partial\s+recovery|death)',
            r'(favorable\s+outcome|poor\s+outcome)'
        ]
        
        for pattern in outcome_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['outcomes']['status'] = match.group(1)
                break
        
        return data
    
    def extract_textbook_data(self, text: str) -> Dict[str, Any]:
        """Extract structured knowledge from textbooks"""
        data = {
            'document_type': 'textbook',
            'chapters': [],
            'diseases': {},
            'treatments': {},
            'key_concepts': [],
            'tables': [],
            'figures': []
        }
        
        # Extract chapter structure
        chapter_matches = re.finditer(r'Chapter\s+(\d+)[:\.]?\s*([^\n]{1,100})', text, re.IGNORECASE)
        for match in chapter_matches:
            data['chapters'].append({
                'number': int(match.group(1)),
                'title': match.group(2).strip()
            })
        
        # Extract disease definitions
        disease_patterns = [
            r'([A-Z][a-z]+(?:\s+[a-z]+)?)\s+is\s+(?:a|an)\s+([^\.]+disease[^\.]+)',
            r'([A-Z][a-z]+(?:\s+[a-z]+)?)\s+(?:syndrome|disorder)\s+characterized\s+by\s+([^\.]+)'
        ]
        
        for pattern in disease_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                disease_name = match.group(1)
                if disease_name not in data['diseases']:
                    data['diseases'][disease_name] = {
                        'definition': match.group(2).strip(),
                        'symptoms': [],
                        'treatments': []
                    }
        
        # Extract diagnostic criteria
        criteria_match = re.search(r'diagnostic\s+criteria[:\s]+([^\.]{20,500})', text, re.IGNORECASE)
        if criteria_match:
            data['key_concepts'].append({
                'type': 'diagnostic_criteria',
                'content': criteria_match.group(1).strip()
            })
        
        # Extract treatment protocols
        treatment_patterns = [
            r'treatment\s+(?:includes|consists\s+of|involves)\s+([^\.]+)',
            r'first[\s\-]line\s+(?:treatment|therapy)\s+(?:is|includes)\s+([^\.]+)'
        ]
        
        for pattern in treatment_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                treatment = match.group(1).strip()
                if len(treatment) < 200:  # Avoid overly long captures
                    if 'general' not in data['treatments']:
                        data['treatments']['general'] = []
                    data['treatments']['general'].append(treatment)
        
        # Extract key points or summaries
        keypoint_patterns = [
            r'(?:key\s+points?|summary|important\s+points?)[:\s]+([^\.]{20,500})',
            r'(?:remember|note)\s+that\s+([^\.]{20,200})'
        ]
        
        for pattern in keypoint_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                data['key_concepts'].append({
                    'type': 'key_point',
                    'content': match.group(1).strip()
                })
        
        return data
    
    def extract_guideline_data(self, text: str) -> Dict[str, Any]:
        """Extract recommendations and protocols from guidelines"""
        data = {
            'document_type': 'clinical_guideline',
            'recommendations': [],
            'algorithms': [],
            'evidence_levels': {},
            'contraindications': [],
            'monitoring': []
        }
        
        # Extract recommendations with evidence levels
        rec_patterns = [
            r'(recommend[s|ed]?|should\s+be|must\s+be)\s+([^\.]+)',
            r'Level\s+([A-C])\s+(?:evidence|recommendation)[:\s]+([^\.]+)'
        ]
        
        for pattern in rec_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) == 2:
                    if match.group(1).startswith('Level'):
                        data['recommendations'].append({
                            'text': match.group(2).strip(),
                            'evidence_level': match.group(1)
                        })
                    else:
                        data['recommendations'].append({
                            'text': match.group(2).strip(),
                            'strength': match.group(1)
                        })
        
        # Extract contraindications
        contra_patterns = [
            r'contraindicated\s+in\s+([^\.]+)',
            r'should\s+not\s+be\s+(?:used|given)\s+(?:in|to)\s+([^\.]+)',
            r'avoid\s+(?:in|for)\s+([^\.]+)'
        ]
        
        for pattern in contra_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                data['contraindications'].append(match.group(1).strip())
        
        # Extract monitoring requirements
        monitor_patterns = [
            r'monitor\s+([^\.]+)',
            r'check\s+([^\.]+)\s+(?:every|daily|weekly)',
            r'follow[\s\-]up\s+([^\.]+)'
        ]
        
        for pattern in monitor_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                monitoring_item = match.group(1).strip()
                if len(monitoring_item) < 100:
                    data['monitoring'].append(monitoring_item)
        
        return data
    
    def extract_discharge_summary_data(self, text: str) -> Dict[str, Any]:
        """Extract data from discharge summaries"""
        data = {
            'document_type': 'discharge_summary',
            'admission': {},
            'discharge': {},
            'hospital_course': '',
            'medications': {'admission': [], 'discharge': []},
            'follow_up': []
        }
        
        # Admission and discharge dates
        admit_match = re.search(r'admission\s+date[:\s]+([^\n]+)', text, re.IGNORECASE)
        if admit_match:
            data['admission']['date'] = admit_match.group(1).strip()
        
        discharge_match = re.search(r'discharge\s+date[:\s]+([^\n]+)', text, re.IGNORECASE)
        if discharge_match:
            data['discharge']['date'] = discharge_match.group(1).strip()
        
        # Diagnoses
        admit_dx_match = re.search(r'admission\s+diagnosis[:\s]+([^\n]+)', text, re.IGNORECASE)
        if admit_dx_match:
            data['admission']['diagnosis'] = admit_dx_match.group(1).strip()
        
        discharge_dx_match = re.search(r'discharge\s+diagnosis[:\s]+([^\n]+)', text, re.IGNORECASE)
        if discharge_dx_match:
            data['discharge']['diagnosis'] = discharge_dx_match.group(1).strip()
        
        # Hospital course
        course_match = re.search(r'hospital\s+course[:\s]+([^\.]{50,1000})', text, re.IGNORECASE)
        if course_match:
            data['hospital_course'] = course_match.group(1).strip()
        
        # Discharge medications
        self._extract_discharge_medications(text, data)
        
        # Follow-up instructions
        followup_match = re.search(r'follow[\s\-]up[:\s]+([^\.]{20,500})', text, re.IGNORECASE)
        if followup_match:
            data['follow_up'].append(followup_match.group(1).strip())
        
        return data
    
    def extract_lab_report_data(self, text: str) -> Dict[str, Any]:
        """Extract structured lab values"""
        data = {
            'document_type': 'lab_report',
            'tests': [],
            'abnormal_values': [],
            'critical_values': []
        }
        
        # Pattern for lab values: Test Name: Value Unit (Reference Range)
        lab_pattern = r'([A-Za-z\s]+):\s*([\d.]+)\s*([a-zA-Z/%]+)?\s*(?:\(|Reference:)?\s*([\d.\-\s]+)?'
        
        matches = re.finditer(lab_pattern, text)
        for match in matches:
            test = {
                'name': match.group(1).strip(),
                'value': match.group(2),
                'unit': match.group(3) if match.group(3) else '',
                'reference': match.group(4) if match.group(4) else ''
            }
            
            # Check if abnormal
            if re.search(r'\b[HL]\b|\*|abnormal|critical', match.group(0), re.IGNORECASE):
                data['abnormal_values'].append(test)
                if 'critical' in match.group(0).lower():
                    data['critical_values'].append(test)
            
            data['tests'].append(test)
        
        return data
    
    def _extract_lab_values(self, text: str, data: Dict):
        """Helper to extract laboratory values with trends"""
        # Platelet counts
        platelet_matches = re.findall(r'platelet[s]?\s*[:=]?\s*([\d,]+)', text, re.IGNORECASE)
        if platelet_matches:
            values = []
            for v in platelet_matches:
                try:
                    val = int(v.replace(',', ''))
                    if 1000 <= val <= 1000000:
                        values.append(val)
                except:
                    continue
            
            if values:
                data['diagnostics']['platelets'] = {
                    'values': values,
                    'trend': 'decreasing' if len(values) > 1 and values[-1] < values[0] else 'stable'
                }
        
        # WBC counts
        wbc_matches = re.findall(r'(?:WBC|white\s+blood\s+cell)[s]?\s*[:=]?\s*([\d,]+)', text, re.IGNORECASE)
        if wbc_matches:
            values = []
            for v in wbc_matches:
                try:
                    val = int(v.replace(',', ''))
                    if 100 <= val <= 100000:
                        values.append(val)
                except:
                    continue
            
            if values:
                data['diagnostics']['wbc'] = {'values': values}
    
    def _extract_medications(self, text: str, data: Dict):
        """Helper to extract medications"""
        med_patterns = [
            r'([A-Z][a-z]+(?:in|ol|ide|ate|ine|one|am))\s+(\d+)\s*(mg|g|ml)',
            r'(acetaminophen|ibuprofen|aspirin|paracetamol)\s+(\d+)\s*(mg)'
        ]
        
        medications = []
        for pattern in med_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) >= 3:
                    medications.append({
                        'name': match[0],
                        'dose': match[1],
                        'unit': match[2]
                    })
        
        if medications:
            data['interventions']['medications'] = medications
    
    def _extract_discharge_medications(self, text: str, data: Dict):
        """Extract medication list from discharge summary"""
        # Look for medication section
        med_section = re.search(r'discharge\s+medications?[:\s]+([^\.]{50,2000})', text, re.IGNORECASE)
        if med_section:
            med_text = med_section.group(1)
            # Parse individual medications
            med_lines = re.findall(r'([A-Z][a-z]+(?:in|ol|ide|ate)?)\s+(\d+)\s*(mg|g)', med_text)
            for med in med_lines:
                data['medications']['discharge'].append({
                    'name': med[0],
                    'dose': f"{med[1]} {med[2]}"
                })
    
    def create_specialized_chunks(self, text: str, doc_type: DocumentType, metadata: Dict) -> List[Dict]:
        """Create chunks optimized for specific document types"""
        chunks = []
        
        if doc_type == DocumentType.CASE_REPORT:
            # Patient-centric chunks with temporal context
            chunk_size = 512
            overlap = 128
        elif doc_type == DocumentType.TEXTBOOK:
            # Concept-centric chunks with hierarchical context
            chunk_size = 768  # Larger for comprehensive concepts
            overlap = 200
        elif doc_type == DocumentType.CLINICAL_GUIDELINE:
            # Recommendation-centric chunks
            chunk_size = 400  # Smaller for precise recommendations
            overlap = 100
        elif doc_type == DocumentType.LAB_REPORT:
            # Value-centric small chunks
            chunk_size = 256
            overlap = 50
        else:
            # Default chunking
            chunk_size = 512
            overlap = 128
        
        sentences = text.replace('\n', ' ').split('. ')
        current_chunk = ""
        chunk_id = 0
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append({
                        'chunk_id': f"{metadata.get('doc_id', 'unknown')}_{chunk_id}",
                        'text': current_chunk.strip(),
                        'metadata': {
                            **metadata,
                            'chunk_index': chunk_id,
                            'chunk_type': 'text',
                            'document_type': doc_type.value
                        }
                    })
                    chunk_id += 1
                    
                    # Overlap for context continuity
                    if len(current_chunk) > overlap:
                        current_chunk = current_chunk[-overlap:] + sentence + ". "
                    else:
                        current_chunk = sentence + ". "
        
        # Add final chunk
        if current_chunk:
            chunks.append({
                'chunk_id': f"{metadata.get('doc_id', 'unknown')}_{chunk_id}",
                'text': current_chunk.strip(),
                'metadata': {
                    **metadata,
                    'chunk_index': chunk_id,
                    'chunk_type': 'text',
                    'document_type': doc_type.value
                }
            })
        
        return chunks
    
    def extract_images_with_context(self, doc, base_name, output_dir, doc_type: DocumentType) -> List[Dict]:
        """Extract images with document-type-specific context"""
        extracted_images = []
        
        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n > 3:
                        pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                        pix = pix_rgb
                    
                    img_hash = hashlib.md5(pix.samples).hexdigest()[:8]
                    img_filename = f"{base_name}_p{page_num+1}_img{img_index+1}_{img_hash}.png"
                    img_path = os.path.join(output_dir, img_filename)
                    pix.save(img_path)
                    
                    # Extract figure caption based on document type
                    caption = self._extract_figure_caption(page_text, img_index, doc_type)
                    
                    # Assess clinical relevance based on document type
                    relevance = self._assess_image_relevance(caption, doc_type)
                    
                    img_info = {
                        'filename': img_filename,
                        'page': page_num + 1,
                        'index': img_index + 1,
                        'width': pix.width,
                        'height': pix.height,
                        'path': img_path,
                        'caption': caption,
                        'clinical_relevance': relevance,
                        'document_type': doc_type.value
                    }
                    extracted_images.append(img_info)
                    
                except Exception as e:
                    print(f"{Fore.YELLOW}   ⚠️ Image extraction issue: {str(e)[:50]}{Style.RESET_ALL}")
        
        return extracted_images
    
    def _extract_figure_caption(self, page_text: str, img_index: int, doc_type: DocumentType) -> str:
        """Extract caption based on document type conventions"""
        caption = ""
        
        if doc_type == DocumentType.CASE_REPORT:
            # Look for "Figure X" patterns
            pattern = rf'(?:Figure|Fig\.?)\s*{img_index+1}[:\.]?\s*([^\n]{{1,200}})'
        elif doc_type == DocumentType.TEXTBOOK:
            # Look for numbered figures with chapter context
            pattern = rf'(?:Figure|Fig\.?)\s*\d+\.{img_index+1}[:\.]?\s*([^\n]{{1,200}})'
        elif doc_type == DocumentType.RADIOLOGY_REPORT:
            # Look for image descriptions
            pattern = rf'(?:Image|View)\s*{img_index+1}[:\.]?\s*([^\n]{{1,200}})'
        else:
            # Generic pattern
            pattern = rf'(?:Figure|Fig\.?|Image|Table)\s*{img_index+1}[:\.]?\s*([^\n]{{1,200}})'
        
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            caption = match.group(1).strip() if match.lastindex else ""
        
        return caption
    
    def _assess_image_relevance(self, caption: str, doc_type: DocumentType) -> str:
        """Assess image relevance based on document type"""
        caption_lower = caption.lower()
        
        if doc_type == DocumentType.CASE_REPORT:
            if any(term in caption_lower for term in ['rash', 'lesion', 'eruption']):
                return 'clinical_finding'
            elif any(term in caption_lower for term in ['ct', 'mri', 'xray']):
                return 'diagnostic_imaging'
        elif doc_type == DocumentType.TEXTBOOK:
            if any(term in caption_lower for term in ['algorithm', 'flowchart']):
                return 'clinical_algorithm'
            elif any(term in caption_lower for term in ['anatomy', 'structure']):
                return 'anatomical_diagram'
        elif doc_type == DocumentType.LAB_REPORT:
            if any(term in caption_lower for term in ['graph', 'trend', 'plot']):
                return 'data_visualization'
        
        return 'clinical_documentation'
    
    def process_pdf(self, pdf_path: str, progress_callback=None) -> Optional[str]:
        """Process PDF with intelligent document type detection"""
        
        filename = os.path.basename(pdf_path)
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"📄 Processing: {filename}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        try:
            doc = fitz.open(pdf_path)
            base_name = Path(pdf_path).stem
            doc_id = hashlib.md5(base_name.encode()).hexdigest()[:12]
            page_count = len(doc)
            
            # Extract text for analysis
            if progress_callback:
                progress_callback("Extracting text for analysis...")
            
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            
            # INTELLIGENT DOCUMENT CLASSIFICATION
            if progress_callback:
                progress_callback("Detecting document type...")
            
            doc_type, confidence = self.classify_document(full_text, page_count)
            
            print(f"📋 Document Type: {Fore.GREEN}{doc_type.value}{Style.RESET_ALL} (confidence: {confidence:.0%})")
            
            # Create output folder based on document type
            case_folder = os.path.join(self.output_dir, f"{doc_type.value}_{base_name}")
            os.makedirs(case_folder, exist_ok=True)
            os.makedirs(os.path.join(case_folder, "images"), exist_ok=True)
            
            # APPLY SPECIALIZED EXTRACTION BASED ON TYPE
            if progress_callback:
                progress_callback(f"Applying {doc_type.value} extraction strategy...")
            
            if doc_type == DocumentType.CASE_REPORT:
                extracted_data = self.extract_case_report_data(full_text)
            elif doc_type == DocumentType.TEXTBOOK:
                extracted_data = self.extract_textbook_data(full_text)
            elif doc_type == DocumentType.CLINICAL_GUIDELINE:
                extracted_data = self.extract_guideline_data(full_text)
            elif doc_type == DocumentType.DISCHARGE_SUMMARY:
                extracted_data = self.extract_discharge_summary_data(full_text)
            elif doc_type == DocumentType.LAB_REPORT:
                extracted_data = self.extract_lab_report_data(full_text)
            else:
                # Fallback to generic extraction
                extracted_data = self.extract_case_report_data(full_text)
            
            # Extract images with type-specific context
            if progress_callback:
                progress_callback("Extracting images with context...")
            
            images = self.extract_images_with_context(
                doc, base_name, os.path.join(case_folder, "images"), doc_type
            )
            
            # Create metadata
            doc_metadata = {
                'doc_id': doc_id,
                'filename': filename,
                'document_type': doc_type.value,
                'type_confidence': confidence,
                'pages': page_count,
                'processed_date': datetime.now().isoformat(),
                'has_images': len(images) > 0,
                'image_count': len(images)
            }
            
            # Create specialized chunks
            if progress_callback:
                progress_callback("Creating optimized vector chunks...")
            
            text_chunks = self.create_specialized_chunks(full_text, doc_type, doc_metadata)
            
            # Create image chunks
            image_chunks = []
            for img in images:
                image_chunks.append({
                    'chunk_id': f"{doc_id}_img_{img['index']}",
                    'text': f"Image: {img.get('caption', '')}",
                    'metadata': {
                        **doc_metadata,
                        'chunk_type': 'image',
                        'image_path': img['filename'],
                        'clinical_relevance': img['clinical_relevance'],
                        'page': img['page']
                    }
                })
            
            # Save outputs
            if progress_callback:
                progress_callback("Saving structured outputs...")
            
            # 1. Vector DB JSON with document type
            vector_db_data = {
                'document_id': doc_id,
                'document_type': doc_type.value,
                'type_confidence': confidence,
                'document_metadata': doc_metadata,
                'extracted_data': extracted_data,
                'text_chunks': text_chunks,
                'image_chunks': image_chunks,
                'total_chunks': len(text_chunks) + len(image_chunks)
            }
            
            vector_db_path = os.path.join(case_folder, f"{base_name}_vector_db.json")
            with open(vector_db_path, 'w', encoding='utf-8') as f:
                json.dump(vector_db_data, f, indent=2, ensure_ascii=False)
            
            # 2. Type-specific summary
            summary_path = os.path.join(case_folder, f"{base_name}_summary.md")
            self._create_type_specific_summary(summary_path, extracted_data, images, doc_metadata, doc_type)
            
            # 3. Extraction report
            report_path = os.path.join(case_folder, "extraction_report.json")
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'document_type': doc_type.value,
                    'confidence': confidence,
                    'extraction_stats': {
                        'total_pages': page_count,
                        'text_chunks': len(text_chunks),
                        'image_chunks': len(image_chunks),
                        'extracted_fields': len(extracted_data)
                    }
                }, f, indent=2)
            
            doc.close()
            
            print(f"{Fore.GREEN}✅ Successfully processed as {doc_type.value}!{Style.RESET_ALL}")
            print(f"   📊 {len(text_chunks)} text chunks")
            print(f"   🖼️  {len(image_chunks)} image chunks")
            print(f"   📁 Output: {case_folder}")
            
            self.processed_files.append({
                'file': filename,
                'type': doc_type.value,
                'confidence': confidence,
                'folder': case_folder,
                'chunks': len(text_chunks) + len(image_chunks)
            })
            
            return case_folder
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
            self.failed_files.append({'file': filename, 'error': str(e)})
            return None
    
    def _create_type_specific_summary(self, path: str, data: Dict, images: List, 
                                     metadata: Dict, doc_type: DocumentType):
        """Create document-type-specific summary"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# {doc_type.value.replace('_', ' ').title()} Summary\n\n")
            f.write(f"**Document:** {metadata['filename']}\n")
            f.write(f"**Type:** {doc_type.value} (confidence: {metadata['type_confidence']:.0%})\n")
            f.write(f"**Processed:** {metadata['processed_date']}\n\n")
            
            if doc_type == DocumentType.CASE_REPORT:
                self._write_case_report_summary(f, data)
            elif doc_type == DocumentType.TEXTBOOK:
                self._write_textbook_summary(f, data)
            elif doc_type == DocumentType.CLINICAL_GUIDELINE:
                self._write_guideline_summary(f, data)
            elif doc_type == DocumentType.DISCHARGE_SUMMARY:
                self._write_discharge_summary(f, data)
            elif doc_type == DocumentType.LAB_REPORT:
                self._write_lab_report_summary(f, data)
            
            # Add images section
            if images:
                f.write("\n## 🖼️ Extracted Images\n\n")
                for img in images[:10]:  # Limit to first 10
                    f.write(f"- **Image {img['index']}** (Page {img['page']}): ")
                    f.write(f"{img.get('caption', 'No caption')} ")
                    f.write(f"[{img['clinical_relevance']}]\n")
    
    def _write_case_report_summary(self, f, data: Dict):
        """Write case report specific summary"""
        if data.get('patient'):
            f.write("## Patient Demographics\n")
            for key, value in data['patient'].items():
                f.write(f"- **{key.title()}:** {value}\n")
            f.write("\n")
        
        if data.get('timeline'):
            f.write("## Timeline\n")
            for key, value in data['timeline'].items():
                f.write(f"- **{key.replace('_', ' ').title()}:** {value}\n")
            f.write("\n")
        
        if data.get('diagnostics'):
            f.write("## Diagnostics\n")
            for key, value in data['diagnostics'].items():
                if isinstance(value, dict):
                    f.write(f"- **{key.title()}:** {value}\n")
                else:
                    f.write(f"- **{key.title()}:** {value}\n")
            f.write("\n")
    
    def _write_textbook_summary(self, f, data: Dict):
        """Write textbook specific summary"""
        if data.get('chapters'):
            f.write("## Chapter Structure\n")
            for chapter in data['chapters'][:10]:
                f.write(f"- Chapter {chapter['number']}: {chapter['title']}\n")
            f.write("\n")
        
        if data.get('diseases'):
            f.write("## Disease Entities\n")
            for disease, info in list(data['diseases'].items())[:5]:
                f.write(f"### {disease}\n")
                f.write(f"{info.get('definition', 'No definition')}\n\n")
        
        if data.get('key_concepts'):
            f.write("## Key Concepts\n")
            for concept in data['key_concepts'][:5]:
                f.write(f"- **{concept['type']}:** {concept['content'][:200]}...\n")
            f.write("\n")
    
    def _write_guideline_summary(self, f, data: Dict):
        """Write guideline specific summary"""
        if data.get('recommendations'):
            f.write("## Recommendations\n")
            for rec in data['recommendations'][:10]:
                if 'evidence_level' in rec:
                    f.write(f"- [{rec['evidence_level']}] {rec['text']}\n")
                else:
                    f.write(f"- {rec['text']}\n")
            f.write("\n")
        
        if data.get('contraindications'):
            f.write("## Contraindications\n")
            for contra in data['contraindications'][:5]:
                f.write(f"- {contra}\n")
            f.write("\n")
    
    def _write_discharge_summary(self, f, data: Dict):
        """Write discharge summary specific content"""
        if data.get('admission'):
            f.write("## Admission\n")
            for key, value in data['admission'].items():
                f.write(f"- **{key.title()}:** {value}\n")
            f.write("\n")
        
        if data.get('discharge'):
            f.write("## Discharge\n")
            for key, value in data['discharge'].items():
                f.write(f"- **{key.title()}:** {value}\n")
            f.write("\n")
        
        if data.get('medications', {}).get('discharge'):
            f.write("## Discharge Medications\n")
            for med in data['medications']['discharge'][:10]:
                f.write(f"- {med.get('name', 'Unknown')} {med.get('dose', '')}\n")
            f.write("\n")
    
    def _write_lab_report_summary(self, f, data: Dict):
        """Write lab report specific summary"""
        if data.get('abnormal_values'):
            f.write("## Abnormal Values\n")
            for test in data['abnormal_values'][:10]:
                f.write(f"- **{test['name']}:** {test['value']} {test.get('unit', '')}\n")
            f.write("\n")
        
        if data.get('critical_values'):
            f.write("## ⚠️ Critical Values\n")
            for test in data['critical_values']:
                f.write(f"- **{test['name']}:** {test['value']} {test.get('unit', '')}\n")
            f.write("\n")
    
    def create_master_report(self):
        """Create comprehensive report of all processed documents"""
        report_path = os.path.join(self.output_dir, "MASTER_REPORT.md")
        
        # Group by document type
        by_type = defaultdict(list)
        for proc in self.processed_files:
            by_type[proc['type']].append(proc)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Intelligent PDF Processing Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Output Directory:** `{self.output_dir}`\n\n")
            
            f.write("## 📊 Summary Statistics\n\n")
            f.write(f"- **Total Files Processed:** {len(self.processed_files)}\n")
            f.write(f"- **Failed Files:** {len(self.failed_files)}\n\n")
            
            f.write("### Document Type Distribution\n\n")
            for doc_type, files in by_type.items():
                f.write(f"- **{doc_type.replace('_', ' ').title()}:** {len(files)} files\n")
            f.write("\n")
            
            # Detailed breakdown by type
            for doc_type, files in by_type.items():
                if files:
                    f.write(f"## {doc_type.replace('_', ' ').title()} Files\n\n")
                    for proc in files:
                        f.write(f"### 📄 {proc['file']}\n")
                        f.write(f"- **Confidence:** {proc['confidence']:.0%}\n")
                        f.write(f"- **Chunks:** {proc['chunks']}\n")
                        f.write(f"- **Folder:** `{os.path.basename(proc['folder'])}`\n\n")
            
            if self.failed_files:
                f.write("## ❌ Failed Files\n\n")
                for fail in self.failed_files:
                    f.write(f"- **{fail['file']}:** {fail['error'][:100]}\n")
        
        # Create JSON index
        index_path = os.path.join(self.output_dir, "document_index.json")
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump({
                'processing_date': datetime.now().isoformat(),
                'statistics': {
                    'total_processed': len(self.processed_files),
                    'by_type': {k: len(v) for k, v in by_type.items()},
                    'total_failed': len(self.failed_files)
                },
                'documents': self.processed_files,
                'failed': self.failed_files
            }, f, indent=2)
        
        return report_path


def main():
    """Main entry point with GUI support"""
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}🧠 INTELLIGENT CLINICAL PDF PROCESSOR{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Auto-detects: Case Reports, Textbooks, Guidelines, & More{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    if len(sys.argv) > 1:
        # Command line mode
        print("📋 Command Line Mode\n")
        
        pdf_files = [f for f in sys.argv[1:] if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            print(f"{Fore.RED}❌ No PDF files provided{Style.RESET_ALL}")
            print("\nUsage: python intelligent_processor.py file1.pdf file2.pdf ...")
            sys.exit(1)
        
        print(f"Found {len(pdf_files)} PDF file(s)\n")
        
        extractor = IntelligentClinicalExtractor()
        
        for pdf in tqdm(pdf_files, desc="Processing PDFs"):
            if os.path.exists(pdf):
                extractor.process_pdf(pdf)
            else:
                print(f"{Fore.RED}❌ File not found: {pdf}{Style.RESET_ALL}")
        
        # Create report
        report_path = extractor.create_master_report()
        
        print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}✅ INTELLIGENT PROCESSING COMPLETE!{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
        print(f"\n📁 Output: {extractor.output_dir}")
        print(f"📊 Processed: {len(extractor.processed_files)} files")
        
        # Show type distribution
        from collections import Counter
        types = Counter(f['type'] for f in extractor.processed_files)
        for doc_type, count in types.items():
            print(f"   - {doc_type}: {count} files")
        
        if platform.system() == 'Windows':
            response = input("\nOpen output folder? (y/n): ")
            if response.lower() == 'y':
                os.startfile(extractor.output_dir)
    
    elif GUI_AVAILABLE:
        # GUI mode
        print("🖼️  Starting GUI Mode...\n")
        
        class IntelligentGUI:
            def __init__(self):
                self.root = tk.Tk()
                self.root.title("Intelligent Clinical PDF Processor")
                self.root.geometry("800x600")
                
                self.extractor = None
                self.selected_files = []
                self.setup_ui()
            
            def setup_ui(self):
                # Title
                title_frame = tk.Frame(self.root, bg='#34495e', height=70)
                title_frame.pack(fill='x')
                title_frame.pack_propagate(False)
                
                title_label = tk.Label(
                    title_frame,
                    text="🧠 Intelligent Clinical PDF Processor",
                    font=('Arial', 20, 'bold'),
                    bg='#34495e',
                    fg='white'
                )
                title_label.pack(pady=20)
                
                # Main content
                main_frame = tk.Frame(self.root, padx=20, pady=20)
                main_frame.pack(fill='both', expand=True)
                
                # File selection
                file_frame = tk.LabelFrame(main_frame, text="Select PDF Files", padx=10, pady=10)
                file_frame.pack(fill='x', pady=(0, 10))
                
                self.file_label = tk.Label(file_frame, text="No files selected", anchor='w')
                self.file_label.pack(side='left', fill='x', expand=True)
                
                tk.Button(
                    file_frame,
                    text="Browse Files",
                    command=self.select_files,
                    bg='#3498db',
                    fg='white',
                    padx=20
                ).pack(side='right')
                
                # Progress
                progress_frame = tk.LabelFrame(main_frame, text="Processing Log", padx=10, pady=10)
                progress_frame.pack(fill='both', expand=True)
                
                self.progress_text = tk.Text(progress_frame, wrap='word')
                self.progress_text.pack(fill='both', expand=True)
                
                # Process button
                self.process_btn = tk.Button(
                    main_frame,
                    text="🚀 Process with Intelligence",
                    command=self.process_files,
                    bg='#27ae60',
                    fg='white',
                    font=('Arial', 14, 'bold'),
                    pady=10,
                    state='disabled'
                )
                self.process_btn.pack(fill='x', pady=(10, 0))
            
            def select_files(self):
                files = filedialog.askopenfilenames(
                    title="Select PDF Files",
                    filetypes=[("PDF files", "*.pdf")]
                )
                if files:
                    self.selected_files = list(files)
                    self.file_label.config(text=f"{len(files)} file(s) selected")
                    self.process_btn.config(state='normal')
                    self.log(f"Selected {len(files)} files")
            
            def log(self, message):
                self.progress_text.insert('end', f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
                self.progress_text.see('end')
                self.root.update()
            
            def process_files(self):
                self.process_btn.config(state='disabled')
                
                def worker():
                    self.extractor = IntelligentClinicalExtractor()
                    
                    for pdf in self.selected_files:
                        self.log(f"\nProcessing: {os.path.basename(pdf)}")
                        result = self.extractor.process_pdf(pdf, lambda msg: self.log(f"  → {msg}"))
                        
                        if result:
                            # Get document type from processed files
                            last_processed = self.extractor.processed_files[-1]
                            self.log(f"  ✅ Detected as: {last_processed['type']}")
                            self.log(f"  ✅ Confidence: {last_processed['confidence']:.0%}")
                    
                    self.extractor.create_master_report()
                    self.log("\n✅ All processing complete!")
                    
                    if messagebox.askyesno("Complete", "Processing complete!\n\nOpen output folder?"):
                        os.startfile(self.extractor.output_dir)
                    
                    self.process_btn.config(state='normal')
                
                thread = threading.Thread(target=worker)
                thread.daemon = True
                thread.start()
            
            def run(self):
                self.root.mainloop()
        
        app = IntelligentGUI()
        app.run()
    
    else:
        print("Please provide PDF files as arguments:")
        print("  python intelligent_processor.py file1.pdf file2.pdf ...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⚠️ Interrupted{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
    finally:
        if platform.system() == 'Windows':
            input("\nPress Enter to exit...")
