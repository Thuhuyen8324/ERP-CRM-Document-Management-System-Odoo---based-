# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError

class BaoGia(models.Model):
    _name = "bao_gia"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Báo giá khách hàng"
    _rec_name = 'so_bao_gia'

    so_bao_gia = fields.Char(string="Số báo giá", required=True, copy=False, readonly=True, default=lambda self: 'Mới')
    khach_hang_id = fields.Many2one('khach_hang', string="Khách hàng", ondelete='cascade')
    nhan_vien_id = fields.Many2one('nhan_vien', string="Người lập báo giá")
    ngay_lap = fields.Date(string="Ngày lập", default=fields.Date.today)
    ngay_het_han = fields.Date(string="Ngày hết hạn")

    # --- PHẦN TÍCH HỢP HÀNG HÓA & THUẾ ---
    chi_tiet_ids = fields.One2many('bao_gia_chi_tiet', 'bao_gia_id', string="Chi tiết hàng hóa")
    
    tien_hang_chua_thue = fields.Float(string="Tiền hàng chưa thuế", compute="_compute_totals", store=True)
    
    # TRƯỜNG HIỂN THỊ % GIẢM GIÁ Ở DƯỚI (Khớp với bên trên)
    tong_giam_gia_percent = fields.Float(string="Giảm giá (%)", compute="_compute_totals", store=True)
    
    thue_vat_phan_tram = fields.Selection([
        ('0', '0%'), ('5', '5%'), ('8', '8%'), ('10', '10%')
    ], string="VAT (%)", default='10')
    thue_vat_thanh_tien = fields.Float(string="VAT thành tiền", compute="_compute_totals", store=True)
    
    tong_tien = fields.Float(string="Tổng giá trị (VNĐ)", compute="_compute_totals", store=True, tracking=True)

    @api.depends('chi_tiet_ids.thanh_tien', 'chi_tiet_ids.giam_gia', 'chi_tiet_ids.so_luong', 'chi_tiet_ids.don_gia', 'thue_vat_phan_tram')
    def _compute_totals(self):
        for rec in self:
            tong_chua_giam = sum(line.so_luong * line.don_gia for line in rec.chi_tiet_ids)
            tong_sau_giam = sum(line.thanh_tien for line in rec.chi_tiet_ids)
            
            # Tính % giảm giá thực tế của toàn đơn hàng
            percent = 0.0
            if tong_chua_giam > 0:
                percent = ((tong_chua_giam - tong_sau_giam) / tong_chua_giam) * 100
            
            vat = (tong_sau_giam * float(rec.thue_vat_phan_tram)) / 100
            
            rec.tien_hang_chua_thue = tong_sau_giam
            rec.tong_giam_gia_percent = percent
            rec.thue_vat_thanh_tien = vat
            rec.tong_tien = tong_sau_giam + vat

    trang_thai = fields.Selection([
        ('du_thao', 'Dự thảo'),
        ('da_gui', 'Đã gửi khách'),
        ('chap_nhan', 'Chấp nhận'),
        ('tu_choi', 'Từ chối'),
    ], string='Trạng thái', default='du_thao', tracking=True)

    ghi_chu = fields.Text(string="Điều khoản thương mại")

    @api.model
    def create(self, vals):
        if vals.get('so_bao_gia', 'Mới') == 'Mới':
            vals['so_bao_gia'] = self.env['ir.sequence'].next_by_code('bao_gia.code') or 'Mới'
        return super(BaoGia, self).create(vals)

    def action_gui_mail_bao_gia(self):
        self.ensure_one()
        if not self.khach_hang_id.email:
            raise UserError("Khách hàng chưa có địa chỉ Email!")

        items_html = ""
        for line in self.chi_tiet_ids:
            items_html += f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">{line.ten_hien_thi}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{line.so_luong}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{line.don_gia:,.0f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{line.giam_gia}%</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{line.thanh_tien:,.0f}</td>
                </tr>
            """

        subject = f"THÔNG TIN BÁO GIÁ: {self.so_bao_gia}"
        body_html = f"""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; line-height: 1.6;">
                <p>Chào chị <b>{self.khach_hang_id.name}</b>,</p>
                <p>Công ty <b>AAHK</b> xin gửi tới chị chi tiết báo giá dịch vụ:</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <tr style="background-color: #f2f2f2;">
                        <th style="border: 1px solid #ddd; padding: 8px;">Sản phẩm</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">SL</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Đơn giá</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Giảm %</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Thành tiền</th>
                    </tr>
                    {items_html}
                </table>
                <div style="background: #fff5f5; padding: 15px; border-left: 5px solid #e74c3c; margin: 15px 0;">
                    <p style="margin: 0;"><b>Tổng giảm giá:</b> {self.tong_giam_gia_percent:.2f}%</p>
                    <p style="margin: 0;"><b>Thuế VAT ({self.thue_vat_phan_tram}%):</b> {self.thue_vat_thanh_tien:,.0f} VNĐ</p>
                    <h3 style="margin: 5px 0; color: #e74c3c;">TỔNG CỘNG: {self.tong_tien:,.0f} VNĐ</h3>
                </div>
                 <p>Báo giá có hiệu lực trong vòng 15 ngày. Anh/chị vui lòng kiểm tra và phản hồi sớm giúp công ty.</p>
                <p>Trân trọng,</p>
                <p><b>{self.nhan_vien_id.ho_va_ten if self.nhan_vien_id else 'CÔNG TY AAHK'}</b></p>
            </div>
        """
        # ... (phần còn lại của hàm action_gui_mail_bao_gia giữ nguyên như cũ) ...
        mail_values = {
            'subject': subject,
            'body_html': body_html,
            'email_to': self.khach_hang_id.email,
            'email_from': 'AAHK CSKH <khanhhuyen8324@gmail.com>',
            'reply_to': 'AAHK CSKH <khanhhuyen8324@gmail.com>',
        }
        self.env['mail.mail'].sudo().create(mail_values).send()
        self.trang_thai = 'da_gui'
        return True

class BaoGiaChiTiet(models.Model):
    _name = "bao_gia_chi_tiet"
    _description = "Chi tiết báo giá"

    bao_gia_id = fields.Many2one('bao_gia', ondelete='cascade')
    san_pham_mau = fields.Selection([
        ('tư vấn', 'Dịch vụ tư vấn giải pháp'),
        ('crm', 'Phần mềm quản lý CRM'),
        ('sv', 'Thiết bị Máy chủ Dell'),
        ('bt', 'Bảo trì hệ thống'),
        ('khac', 'Khác (Nhập tay)')
    ], string="Chọn hàng hóa", required=True)

    ten_hien_thi = fields.Char(string="Tên hàng hóa", compute="_compute_info", store=True, readonly=False)
    so_luong = fields.Float(string="Số lượng", default=1.0)
    don_gia = fields.Float(string="Đơn giá", compute="_compute_info", store=True, readonly=False)
    giam_gia = fields.Float(string="Giảm giá (%)", default=0.0)
    thanh_tien = fields.Float(string="Thành tiền", compute="_compute_line_total", store=True)

    @api.depends('san_pham_mau')
    def _compute_info(self):
        prices = {'tư vấn': 5000000, 'crm': 15000000, 'sv': 45000000, 'bt': 10000000, 'khac': 0}
        for rec in self:
            rec.don_gia = prices.get(rec.san_pham_mau, 0)
            rec.ten_hien_thi = dict(self._fields['san_pham_mau'].selection).get(rec.san_pham_mau)

    @api.depends('so_luong', 'don_gia', 'giam_gia')
    def _compute_line_total(self):
        for line in self:
            tien_chua_giam = line.so_luong * line.don_gia
            so_tien_giam = tien_chua_giam * (line.giam_gia / 100.0)
            line.thanh_tien = tien_chua_giam - so_tien_giam
# # -*- coding: utf-8 -*- # bản chuẩn nhé
# from odoo import fields, models, api, _
# from odoo.exceptions import UserError


# class BaoGia(models.Model):
#     _name = "bao_gia"
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#     _description = "Báo giá khách hàng"
#     _rec_name = 'so_bao_gia'

#     so_bao_gia = fields.Char(
#         string="Số báo giá",
#         required=True,
#         copy=False,
#         readonly=True,
#         default=lambda self: 'Mới'
#     )
#     khach_hang_id = fields.Many2one(
#         'khach_hang',
#         string="Khách hàng",
#         ondelete='cascade'
#     )
#     nhan_vien_id = fields.Many2one(
#         'nhan_vien',
#         string="Người lập báo giá"
#     )

#     ngay_lap = fields.Date(
#         string="Ngày lập",
#         default=fields.Date.today
#     )
#     ngay_het_han = fields.Date(string="Ngày hết hạn")

#     tong_tien = fields.Float(
#         string="Tổng giá trị (VNĐ)",
#         required=True
#     )

#     trang_thai = fields.Selection([
#         ('du_thao', 'Dự thảo'),
#         ('da_gui', 'Đã gửi khách'),
#         ('chap_nhan', 'Chấp nhận'),
#         ('tu_choi', 'Từ chối'),
#     ], string='Trạng thái', default='du_thao', tracking=True)

#     ghi_chu = fields.Text(string="Điều khoản thương mại")

#     @api.model
#     def create(self, vals):
#         if vals.get('so_bao_gia', 'Mới') == 'Mới':
#             vals['so_bao_gia'] = self.env['ir.sequence'].next_by_code('bao_gia.code') or 'Mới'
#         return super(BaoGia, self).create(vals)

#     def action_gui_mail_bao_gia(self):
#         self.ensure_one()

#         if not self.khach_hang_id.email:
#             raise UserError("Khách hàng chưa có địa chỉ Email!")

#         subject = f"THÔNG TIN BÁO GIÁ: {self.so_bao_gia}"

#         body_html = f"""
#             <div style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; line-height: 1.6;">
#                 <p>Chào chị <b>{self.khach_hang_id.name}</b>,</p>

#                 <p>Công ty <b>AAHK</b> xin gửi tới anh/chị thông tin chi tiết báo giá dịch vụ:</p>

#                 <div style="background: #fff5f5; padding: 20px;
#                             border-left: 5px solid #e74c3c;
#                             margin: 15px 0; border-radius: 4px;">
#                     <h3 style="margin-top: 0; color: #e74c3c;">
#                         CHI TIẾT BÁO GIÁ
#                     </h3>
#                     <ul style="list-style: none; padding: 0;">
#                         <li><b>Mã báo giá:</b> {self.so_bao_gia}</li>
#                         <li>
#                             <b>Tổng giá trị:</b>
#                             <span style="font-size: 18px; color: #e74c3c; font-weight: bold;">
#                                 {self.tong_tien:,.0f} VNĐ
#                             </span>
#                         </li>
#                         <li><b>Ngày lập:</b>
#                             {self.ngay_lap.strftime('%d/%m/%Y') if self.ngay_lap else ''}
#                         </li>
#                     </ul>
#                 </div>

#                 <p>
#                     Báo giá có hiệu lực trong vòng <b>15 ngày</b>.
#                     Chị vui lòng kiểm tra và phản hồi sớm giúp công ty.
#                 </p>

#                 <p>Trân trọng,</p>

#                 <p>
#                     <b>
#                         {self.nhan_vien_id.ho_va_ten if self.nhan_vien_id else 'CÔNG TY AAHK'}
#                     </b><br/>
#                     Phòng Kinh doanh
#                 </p>
#             </div>
#         """

#         # 🔥 CHỖ QUAN TRỌNG NHẤT – FIX NGƯỜI GỬI
#         mail_values = {
#             'subject': subject,
#             'body_html': body_html,
#             'email_to': self.khach_hang_id.email,

#             # 👇 TÊN HIỂN THỊ + EMAIL GỬI
#             'email_from': 'AAHK CSKH <khanhhuyen8324@gmail.com>',
#             'reply_to': 'AAHK CSKH <khanhhuyen8324@gmail.com>',
#         }

#         mail = self.env['mail.mail'].sudo().create(mail_values)
#         mail.send()

#         self.trang_thai = 'da_gui'
#         self.message_post(
#             body=f"Hệ thống AAHK CSKH đã gửi báo giá cho khách hàng {self.khach_hang_id.name}"
#         )

#         return True

