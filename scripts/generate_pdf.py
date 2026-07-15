import os
import json
import sys

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
except ImportError as _rl_err:
    raise ImportError(
        "reportlab is required for PDF generation. "
        "Install it with: pip install reportlab"
    ) from _rl_err

def build_pdf(json_path, pdf_path):
    # Load JSON resume data
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"build_pdf: JSON resume not found at {json_path}")
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Page setup - letter size with 0.4 inch margins to maximize usable area for single page
    margin = 28.8  # 0.4 inches in points (72 * 0.4)
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin
    )
    
    # Styles Setup
    styles = getSampleStyleSheet()
    
    # Custom palette
    primary_color = colors.HexColor("#1A365D")   # Premium Deep Navy
    secondary_color = colors.HexColor("#4A5568") # Elegant Slate Gray
    text_color = colors.HexColor("#2D3748")      # Soft Charcoal Black
    line_color = colors.HexColor("#CBD5E0")      # Divider gray
    
    # Typography Styles
    title_style = ParagraphStyle(
        'NameHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=22,
        textColor=primary_color,
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        'SubTitleHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=secondary_color,
        alignment=TA_CENTER,
        spaceAfter=4
    )
    
    contact_style = ParagraphStyle(
        'ContactHeader',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=10,
        textColor=text_color,
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    summary_style = ParagraphStyle(
        'ProfileSummary',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=11.5,
        textColor=text_color,
        alignment=TA_LEFT
    )
    
    section_title_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        textColor=primary_color,
        spaceBefore=5,
        spaceAfter=1
    )
    
    role_style = ParagraphStyle(
        'JobRole',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=11,
        textColor=primary_color
    )
    
    company_style = ParagraphStyle(
        'JobCompany',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=10,
        leading=11,
        textColor=secondary_color
    )
    
    date_style = ParagraphStyle(
        'JobDates',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10,
        textColor=secondary_color,
        alignment=TA_RIGHT
    )
    
    bullet_style = ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=11.5,
        textColor=text_color,
        leftIndent=10,
        firstLineIndent=-6,
        spaceAfter=2
    )
    
    skill_label_style = ParagraphStyle(
        'SkillLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=11,
        textColor=primary_color
    )
    
    skill_text_style = ParagraphStyle(
        'SkillText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=text_color
    )
    
    story = []
    
    # --- HEADER SECTION ---
    p_info = data['personal_info']
    story.append(Paragraph(p_info['name'].upper(), title_style))
    story.append(Paragraph(p_info['title'].upper(), subtitle_style))
    
    # Inline contact details (Phone | Email | LinkedIn | Location)
    contact_parts = [
        f"Phone: {p_info['phone']}",
        f"Email: {p_info['email']}",
        f"<a href='{p_info['linkedin']}' color='#1A365D'>LinkedIn</a>",
        f"Location: {p_info['location']}"
    ]
    contact_text = "  •  ".join(contact_parts)
    story.append(Paragraph(contact_text, contact_style))
    
    # --- PROFESSIONAL SUMMARY ---
    story.append(HRFlowable(width="100%", thickness=1, color=primary_color, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(data['summary'], summary_style))
    
    # Helper to add section headers with an underline
    def add_section_header(title):
        story.append(Spacer(1, 3))
        story.append(Paragraph(title.upper(), section_title_style))
        story.append(HRFlowable(width="100%", thickness=0.8, color=line_color, spaceBefore=1, spaceAfter=4))
        
    # --- WORK EXPERIENCE ---
    add_section_header("Work Experience")
    
    # Limit number of bullet points for space optimization if needed to guarantee single-page rendering
    for i, exp in enumerate(data['work_experience']):
        # Job header: Role/Company on Left, Dates on Right
        left_text = f"<b>{exp['role']}</b>  |  {exp['company']}"
        left_p = Paragraph(left_text, role_style)
        right_p = Paragraph(f"{exp['start_date']} – {exp['end_date']}", date_style)
        
        # Table layout for header: colWidths total = 554.4pt (8.5in * 72 - 2 * 28.8 margin)
        header_table = Table([[left_p, right_p]], colWidths=[420, 134.4])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(header_table)
        
        # Bullet points
        for bullet in exp['bullets']:
            bullet_p = Paragraph(f"• {bullet}", bullet_style)
            story.append(bullet_p)
            
        story.append(Spacer(1, 2))
        
    # --- SKILLS & TOOLS ---
    add_section_header("Core Competencies & Platforms")
    
    skills = data['skills']
    
    # Structure skills into a clean 2-column or 3-column table
    skills_data = [
        [
            Paragraph("Core Expertise:", skill_label_style),
            Paragraph(", ".join(skills['core']), skill_text_style)
        ],
        [
            Paragraph("Platforms & Tools:", skill_label_style),
            Paragraph(", ".join(skills['platforms_and_tools']), skill_text_style)
        ],
        [
            Paragraph("Certifications:", skill_label_style),
            Paragraph(", ".join(skills['certifications']), skill_text_style)
        ]
    ]
    
    skills_table = Table(skills_data, colWidths=[90, 464.4])
    skills_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(skills_table)
    
    # --- EDUCATION ---
    add_section_header("Education")
    
    for edu in data['education']:
        left_text = f"<b>{edu['degree']}</b> in {edu['major']}  |  {edu['institution']}"
        left_p = Paragraph(left_text, role_style)
        right_p = Paragraph(f"Graduated: {edu['graduation_year']}", date_style)
        
        edu_table = Table([[left_p, right_p]], colWidths=[420, 134.4])
        edu_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(edu_table)
        
    # Build Document
    try:
        doc.build(story)
        print(f"Successfully compiled professional PDF resume at: {pdf_path}")
    except Exception as e:
        raise RuntimeError(f"build_pdf: Failed to compile PDF at {pdf_path}: {e}") from e

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_pdf.py <input_json_path> <output_pdf_path>")
        sys.exit(1)
    build_pdf(sys.argv[1], sys.argv[2])
