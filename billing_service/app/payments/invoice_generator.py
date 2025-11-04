"""
Invoice Generator for the LLM API Platform
Generates detailed invoices with usage breakdowns and PDF export
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import logging
from io import BytesIO
import json

# PDF generation imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

logger = logging.getLogger(__name__)


class InvoiceGenerator:
    """Generates professional invoices for billing"""
    
    def __init__(self, company_info: Dict[str, str]):
        """
        Initialize invoice generator
        
        Args:
            company_info: Company information for invoice header
        """
        self.company_info = company_info
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for invoice"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='InvoiceTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a73e8'),
            alignment=TA_CENTER,
        ))
        
        # Company info style
        self.styles.add(ParagraphStyle(
            name='CompanyInfo',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=12,
            alignment=TA_RIGHT,
        ))
        
        # Customer info style
        self.styles.add(ParagraphStyle(
            name='CustomerInfo',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=12,
            alignment=TA_LEFT,
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1a73e8'),
            spaceAfter=12,
        ))
        
        # Total style
        self.styles.add(ParagraphStyle(
            name='Total',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#1a73e8'),
            alignment=TA_RIGHT,
            fontName='Helvetica-Bold',
        ))
    
    def generate_invoice(
        self,
        invoice_data: Dict[str, any],
        customer_info: Dict[str, str],
        format: str = "pdf"
    ) -> bytes:
        """
        Generate invoice in specified format
        
        Args:
            invoice_data: Invoice data from billing system
            customer_info: Customer information
            format: Output format (pdf, json, html)
            
        Returns:
            Invoice content as bytes
        """
        if format == "pdf":
            return self._generate_pdf_invoice(invoice_data, customer_info)
        elif format == "json":
            return self._generate_json_invoice(invoice_data, customer_info)
        elif format == "html":
            return self._generate_html_invoice(invoice_data, customer_info)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _generate_pdf_invoice(
        self,
        invoice_data: Dict[str, any],
        customer_info: Dict[str, str]
    ) -> bytes:
        """Generate PDF invoice"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Container for flowables
        elements = []
        
        # Add invoice header
        elements.extend(self._create_invoice_header(invoice_data, customer_info))
        
        # Add usage summary
        elements.extend(self._create_usage_summary(invoice_data))
        
        # Add line items table
        elements.extend(self._create_line_items_table(invoice_data))
        
        # Add totals section
        elements.extend(self._create_totals_section(invoice_data))
        
        # Add footer
        elements.extend(self._create_invoice_footer(invoice_data))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF content
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return pdf_content
    
    def _create_invoice_header(
        self,
        invoice_data: Dict[str, any],
        customer_info: Dict[str, str]
    ) -> List:
        """Create invoice header section"""
        elements = []
        
        # Invoice title
        elements.append(Paragraph("INVOICE", self.styles['InvoiceTitle']))
        elements.append(Spacer(1, 0.3 * inch))
        
        # Create two-column layout for company and customer info
        company_data = [
            [
                Paragraph(f"<b>{self.company_info['name']}</b>", self.styles['CompanyInfo']),
                Paragraph(f"<b>Bill To:</b>", self.styles['CustomerInfo'])
            ],
            [
                Paragraph(self.company_info['address'], self.styles['CompanyInfo']),
                Paragraph(customer_info.get('name', 'N/A'), self.styles['CustomerInfo'])
            ],
            [
                Paragraph(f"{self.company_info['city']}, {self.company_info['state']} {self.company_info['zip']}", 
                         self.styles['CompanyInfo']),
                Paragraph(customer_info.get('email', 'N/A'), self.styles['CustomerInfo'])
            ],
            [
                Paragraph(self.company_info.get('phone', ''), self.styles['CompanyInfo']),
                Paragraph(customer_info.get('company', ''), self.styles['CustomerInfo'])
            ],
        ]
        
        header_table = Table(company_data, colWidths=[3.5 * inch, 3.5 * inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Invoice details
        invoice_details_data = [
            ["Invoice Number:", invoice_data.get('invoice_id', 'N/A')],
            ["Invoice Date:", datetime.utcnow().strftime('%B %d, %Y')],
            ["Billing Period:", f"{invoice_data['billing_period']['start']} to {invoice_data['billing_period']['end']}"],
            ["Subscription Tier:", invoice_data.get('tier', 'N/A').title()],
        ]
        
        invoice_details_table = Table(invoice_details_data, colWidths=[2 * inch, 5 * inch])
        invoice_details_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(invoice_details_table)
        elements.append(Spacer(1, 0.5 * inch))
        
        return elements
    
    def _create_usage_summary(self, invoice_data: Dict[str, any]) -> List:
        """Create usage summary section"""
        elements = []
        
        elements.append(Paragraph("Usage Summary", self.styles['SectionHeader']))
        
        usage_summary = invoice_data.get('usage_summary', {})
        
        summary_data = [
            ["Total API Requests:", f"{sum(item.get('details', {}).get('requests', 0) for item in invoice_data.get('line_items', []) if item.get('type') == 'usage'):,}"],
            ["Total Tokens Used:", f"{usage_summary.get('total_tokens', 0):,}"],
            ["Included Tokens:", f"{usage_summary.get('included_tokens', 0):,}"],
            ["Overage Tokens:", f"{usage_summary.get('overage_tokens', 0):,}"],
            ["Usage Percentage:", f"{usage_summary.get('usage_percentage', 0):.1f}%"],
        ]
        
        summary_table = Table(summary_data, colWidths=[2.5 * inch, 2 * inch])
        summary_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        return elements
    
    def _create_line_items_table(self, invoice_data: Dict[str, any]) -> List:
        """Create line items table"""
        elements = []
        
        elements.append(Paragraph("Billing Details", self.styles['SectionHeader']))
        
        # Table headers
        headers = ['Description', 'Quantity', 'Unit', 'Unit Price', 'Total']
        
        # Table data
        table_data = [headers]
        
        for item in invoice_data.get('line_items', []):
            if item['type'] == 'subscription':
                row = [
                    item['description'],
                    str(item.get('quantity', 1)),
                    'Month',
                    f"${item.get('unit_price', 0):.2f}",
                    f"${item.get('total', 0):.2f}"
                ]
            elif item['type'] == 'usage':
                details = item.get('details', {})
                row = [
                    item['description'],
                    f"{item.get('quantity', 0):,}",
                    item.get('unit', 'tokens'),
                    f"${item.get('unit_price', 0):.6f}",
                    f"${item.get('total', 0):.2f}"
                ]
            elif item['type'] == 'overage':
                row = [
                    item['description'],
                    f"{item.get('quantity', 0):,}",
                    item.get('unit', 'tokens'),
                    "Variable",
                    f"${item.get('total', 0):.2f}"
                ]
            elif item['type'] == 'credit':
                row = [
                    item['description'],
                    str(item.get('quantity', 1)),
                    '',
                    '',
                    f"${item.get('total', 0):.2f}"
                ]
            else:
                continue
            
            table_data.append(row)
        
        # Create table
        line_items_table = Table(table_data, colWidths=[3 * inch, 1 * inch, 0.8 * inch, 1.2 * inch, 1 * inch])
        
        # Apply table style
        table_style = TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('ALIGN', (3, 0), (4, -1), 'RIGHT'),
            
            # Alternate row coloring
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
        ])
        
        line_items_table.setStyle(table_style)
        elements.append(line_items_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        return elements
    
    def _create_totals_section(self, invoice_data: Dict[str, any]) -> List:
        """Create totals section"""
        elements = []
        
        totals_data = []
        
        # Subtotal
        if 'subtotal' in invoice_data:
            totals_data.append(['Subtotal:', f"${invoice_data['subtotal']:.2f}"])
        
        # Credits
        if invoice_data.get('credits', 0) > 0:
            totals_data.append(['Credits Applied:', f"-${invoice_data['credits']:.2f}"])
        
        # Total
        totals_data.append(['', ''])  # Empty row for spacing
        totals_data.append([
            Paragraph('<b>Total Due:</b>', self.styles['Total']),
            Paragraph(f"<b>${invoice_data.get('total', 0):.2f}</b>", self.styles['Total'])
        ])
        
        totals_table = Table(totals_data, colWidths=[5.5 * inch, 1.5 * inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -2), 10),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
            ('TOPPADDING', (0, -1), (-1, -1), 12),
        ]))
        
        elements.append(totals_table)
        elements.append(Spacer(1, 0.5 * inch))
        
        return elements
    
    def _create_invoice_footer(self, invoice_data: Dict[str, any]) -> List:
        """Create invoice footer"""
        elements = []
        
        # Payment terms
        elements.append(Paragraph("Payment Terms", self.styles['SectionHeader']))
        
        payment_terms = [
            "• Payment is due within 30 days of invoice date",
            "• Overdue accounts may be subject to service suspension",
            "• Questions? Contact billing@llmplatform.com",
        ]
        
        for term in payment_terms:
            elements.append(Paragraph(term, self.styles['Normal']))
            elements.append(Spacer(1, 0.1 * inch))
        
        elements.append(Spacer(1, 0.3 * inch))
        
        # Thank you message
        thank_you = Paragraph(
            "Thank you for your business!",
            ParagraphStyle(
                'ThankYou',
                parent=self.styles['Normal'],
                fontSize=12,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#1a73e8'),
            )
        )
        elements.append(thank_you)
        
        return elements
    
    def _generate_json_invoice(
        self,
        invoice_data: Dict[str, any],
        customer_info: Dict[str, str]
    ) -> bytes:
        """Generate JSON invoice"""
        invoice_json = {
            "invoice": {
                "header": {
                    "invoice_id": invoice_data.get('invoice_id'),
                    "date": datetime.utcnow().isoformat(),
                    "billing_period": invoice_data.get('billing_period'),
                    "tier": invoice_data.get('tier'),
                },
                "company": self.company_info,
                "customer": customer_info,
                "line_items": invoice_data.get('line_items', []),
                "usage_summary": invoice_data.get('usage_summary', {}),
                "totals": {
                    "subtotal": invoice_data.get('subtotal', 0),
                    "credits": invoice_data.get('credits', 0),
                    "total": invoice_data.get('total', 0),
                },
                "generated_at": invoice_data.get('generated_at'),
            }
        }
        
        return json.dumps(invoice_json, indent=2).encode('utf-8')
    
    def _generate_html_invoice(
        self,
        invoice_data: Dict[str, any],
        customer_info: Dict[str, str]
    ) -> bytes:
        """Generate HTML invoice"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Invoice {invoice_id}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    border-bottom: 2px solid #1a73e8;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }}
                .invoice-title {{
                    color: #1a73e8;
                    font-size: 32px;
                    text-align: center;
                    margin: 0;
                }}
                .company-info {{
                    float: right;
                    text-align: right;
                }}
                .customer-info {{
                    float: left;
                }}
                .clear {{
                    clear: both;
                }}
                .section-header {{
                    color: #1a73e8;
                    font-size: 18px;
                    margin-top: 30px;
                    margin-bottom: 15px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                th {{
                    background-color: #f0f0f0;
                    padding: 10px;
                    text-align: left;
                    border: 1px solid #ddd;
                }}
                td {{
                    padding: 8px;
                    border: 1px solid #ddd;
                }}
                .text-right {{
                    text-align: right;
                }}
                .total-row {{
                    font-weight: bold;
                    font-size: 16px;
                    border-top: 2px solid #333;
                }}
                .footer {{
                    margin-top: 50px;
                    text-align: center;
                    color: #666;
                }}
                .thank-you {{
                    color: #1a73e8;
                    font-size: 18px;
                    margin-top: 30px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1 class="invoice-title">INVOICE</h1>
            </div>
            
            <div class="company-customer-section">
                <div class="company-info">
                    <strong>{company_name}</strong><br>
                    {company_address}<br>
                    {company_city}, {company_state} {company_zip}<br>
                    {company_phone}
                </div>
                
                <div class="customer-info">
                    <strong>Bill To:</strong><br>
                    {customer_name}<br>
                    {customer_email}<br>
                    {customer_company}
                </div>
                <div class="clear"></div>
            </div>
            
            <div style="margin-top: 30px;">
                <table style="width: auto;">
                    <tr>
                        <td><strong>Invoice Number:</strong></td>
                        <td>{invoice_id}</td>
                    </tr>
                    <tr>
                        <td><strong>Invoice Date:</strong></td>
                        <td>{invoice_date}</td>
                    </tr>
                    <tr>
                        <td><strong>Billing Period:</strong></td>
                        <td>{billing_period_start} to {billing_period_end}</td>
                    </tr>
                    <tr>
                        <td><strong>Subscription Tier:</strong></td>
                        <td>{tier}</td>
                    </tr>
                </table>
            </div>
            
            <h2 class="section-header">Usage Summary</h2>
            <table>
                <tr>
                    <td>Total API Requests:</td>
                    <td class="text-right">{total_requests:,}</td>
                </tr>
                <tr>
                    <td>Total Tokens Used:</td>
                    <td class="text-right">{total_tokens:,}</td>
                </tr>
                <tr>
                    <td>Included Tokens:</td>
                    <td class="text-right">{included_tokens:,}</td>
                </tr>
                <tr>
                    <td>Overage Tokens:</td>
                    <td class="text-right">{overage_tokens:,}</td>
                </tr>
                <tr>
                    <td>Usage Percentage:</td>
                    <td class="text-right">{usage_percentage:.1f}%</td>
                </tr>
            </table>
            
            <h2 class="section-header">Billing Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>Description</th>
                        <th>Quantity</th>
                        <th>Unit</th>
                        <th>Unit Price</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    {line_items_html}
                </tbody>
            </table>
            
            <table style="width: 300px; float: right;">
                <tr>
                    <td>Subtotal:</td>
                    <td class="text-right">${subtotal:.2f}</td>
                </tr>
                {credits_row}
                <tr class="total-row">
                    <td>Total Due:</td>
                    <td class="text-right">${total:.2f}</td>
                </tr>
            </table>
            <div class="clear"></div>
            
            <div class="footer">
                <h3 class="section-header">Payment Terms</h3>
                <ul style="text-align: left; display: inline-block;">
                    <li>Payment is due within 30 days of invoice date</li>
                    <li>Overdue accounts may be subject to service suspension</li>
                    <li>Questions? Contact billing@llmplatform.com</li>
                </ul>
                <p class="thank-you">Thank you for your business!</p>
            </div>
        </body>
        </html>
        """
        
        # Generate line items HTML
        line_items_html = ""
        total_requests = 0
        
        for item in invoice_data.get('line_items', []):
            if item['type'] == 'usage':
                total_requests += item.get('details', {}).get('requests', 0)
            
            if item['type'] == 'subscription':
                line_items_html += f"""
                <tr>
                    <td>{item['description']}</td>
                    <td class="text-right">{item.get('quantity', 1)}</td>
                    <td>Month</td>
                    <td class="text-right">${item.get('unit_price', 0):.2f}</td>
                    <td class="text-right">${item.get('total', 0):.2f}</td>
                </tr>
                """
            elif item['type'] == 'usage':
                line_items_html += f"""
                <tr>
                    <td>{item['description']}</td>
                    <td class="text-right">{item.get('quantity', 0):,}</td>
                    <td>{item.get('unit', 'tokens')}</td>
                    <td class="text-right">${item.get('unit_price', 0):.6f}</td>
                    <td class="text-right">${item.get('total', 0):.2f}</td>
                </tr>
                """
            elif item['type'] == 'overage':
                line_items_html += f"""
                <tr>
                    <td>{item['description']}</td>
                    <td class="text-right">{item.get('quantity', 0):,}</td>
                    <td>{item.get('unit', 'tokens')}</td>
                    <td class="text-right">Variable</td>
                    <td class="text-right">${item.get('total', 0):.2f}</td>
                </tr>
                """
            elif item['type'] == 'credit':
                line_items_html += f"""
                <tr>
                    <td>{item['description']}</td>
                    <td class="text-right">{item.get('quantity', 1)}</td>
                    <td></td>
                    <td></td>
                    <td class="text-right">${item.get('total', 0):.2f}</td>
                </tr>
                """
        
        # Credits row
        credits_row = ""
        if invoice_data.get('credits', 0) > 0:
            credits_row = f"""
            <tr>
                <td>Credits Applied:</td>
                <td class="text-right">-${invoice_data['credits']:.2f}</td>
            </tr>
            """
        
        # Format the template
        usage_summary = invoice_data.get('usage_summary', {})
        formatted_html = html_template.format(
            invoice_id=invoice_data.get('invoice_id', 'N/A'),
            invoice_date=datetime.utcnow().strftime('%B %d, %Y'),
            billing_period_start=invoice_data['billing_period']['start'],
            billing_period_end=invoice_data['billing_period']['end'],
            tier=invoice_data.get('tier', 'N/A').title(),
            company_name=self.company_info['name'],
            company_address=self.company_info['address'],
            company_city=self.company_info['city'],
            company_state=self.company_info['state'],
            company_zip=self.company_info['zip'],
            company_phone=self.company_info.get('phone', ''),
            customer_name=customer_info.get('name', 'N/A'),
            customer_email=customer_info.get('email', 'N/A'),
            customer_company=customer_info.get('company', ''),
            total_requests=total_requests,
            total_tokens=usage_summary.get('total_tokens', 0),
            included_tokens=usage_summary.get('included_tokens', 0),
            overage_tokens=usage_summary.get('overage_tokens', 0),
            usage_percentage=usage_summary.get('usage_percentage', 0),
            line_items_html=line_items_html,
            subtotal=invoice_data.get('subtotal', 0),
            credits_row=credits_row,
            total=invoice_data.get('total', 0),
        )
        
        return formatted_html.encode('utf-8')


class InvoiceEmailer:
    """Handles invoice email notifications"""
    
    def __init__(self, email_service):
        """
        Initialize invoice emailer
        
        Args:
            email_service: Email service for sending emails
        """
        self.email_service = email_service
    
    async def send_invoice_email(
        self,
        recipient_email: str,
        invoice_pdf: bytes,
        invoice_data: Dict[str, any],
        customer_name: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Send invoice email with PDF attachment
        
        Args:
            recipient_email: Customer email address
            invoice_pdf: PDF invoice content
            invoice_data: Invoice data for email body
            customer_name: Customer name for personalization
            
        Returns:
            Email sending result
        """
        try:
            # Prepare email content
            subject = f"Invoice {invoice_data['invoice_id']} - {invoice_data.get('tier', 'N/A').title()} Subscription"
            
            # Email body
            body_html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <h2 style="color: #1a73e8;">Your LLM Platform Invoice</h2>
                
                <p>Dear {customer_name or 'Valued Customer'},</p>
                
                <p>Please find attached your invoice for the billing period 
                {invoice_data['billing_period']['start']} to {invoice_data['billing_period']['end']}.</p>
                
                <h3>Invoice Summary:</h3>
                <ul>
                    <li><strong>Invoice Number:</strong> {invoice_data['invoice_id']}</li>
                    <li><strong>Total Due:</strong> ${invoice_data.get('total', 0):.2f}</li>
                    <li><strong>Due Date:</strong> {(datetime.utcnow() + timedelta(days=30)).strftime('%B %d, %Y')}</li>
                </ul>
                
                <h3>Usage Summary:</h3>
                <ul>
                    <li><strong>Total Tokens Used:</strong> {invoice_data['usage_summary'].get('total_tokens', 0):,}</li>
                    <li><strong>Usage Percentage:</strong> {invoice_data['usage_summary'].get('usage_percentage', 0):.1f}%</li>
                </ul>
                
                <p>You can also view and download your invoice from your account dashboard.</p>
                
                <p>If you have any questions about this invoice, please don't hesitate to contact 
                our billing team at billing@llmplatform.com.</p>
                
                <p>Thank you for your continued business!</p>
                
                <p>Best regards,<br>
                The LLM Platform Team</p>
            </body>
            </html>
            """
            
            # Send email with attachment
            result = await self.email_service.send_email(
                to=recipient_email,
                subject=subject,
                body_html=body_html,
                attachments=[{
                    'filename': f"invoice_{invoice_data['invoice_id']}.pdf",
                    'content': invoice_pdf,
                    'content_type': 'application/pdf',
                }]
            )
            
            logger.info(f"Sent invoice email to {recipient_email} for invoice {invoice_data['invoice_id']}")
            
            return {
                "success": True,
                "recipient": recipient_email,
                "invoice_id": invoice_data['invoice_id'],
                "message": "Invoice email sent successfully",
            }
            
        except Exception as e:
            logger.error(f"Failed to send invoice email: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to send invoice email",
            }