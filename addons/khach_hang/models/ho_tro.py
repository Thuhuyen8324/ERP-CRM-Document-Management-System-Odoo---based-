# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class HoTroKhachHang(models.Model):
    _name = "ho_tro_khach_hang"
    _description = "Hỗ trợ khách hàng"
    
    # --- ĐIỂM QUAN TRỌNG 1: Kế thừa mail.thread để có tính năng gửi tin nhắn và thông báo ---
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    _rec_name = 'tieu_de'

    tieu_de = fields.Char(string="Tiêu đề yêu cầu", required=True, tracking=True)
    khach_hang_id = fields.Many2one('khach_hang', string="Khách hàng", required=True, tracking=True)
    
    # --- ĐIỂM QUAN TRỌNG 2: Thêm tracking=True để theo dõi lịch sử thay đổi nhân viên ---
    nhan_vien_id = fields.Many2one('nhan_vien', string="Nhân viên xử lý", tracking=True)
    
    ngay_tiep_nhan = fields.Datetime(string="Ngày tiếp nhận", default=fields.Datetime.now)
    ngay_hoan_thanh = fields.Datetime(string="Ngày hoàn thành", tracking=True)
    
    muc_do_uu_tien = fields.Selection([
        ('0', 'Thấp'),
        ('1', 'Trung bình'),
        ('2', 'Cao'),
        ('3', 'Khẩn cấp')
    ], string="Mức độ ưu tiên", default='1', tracking=True)
    
    trang_thai = fields.Selection([
        ('moi', 'Mới tiếp nhận'),
        ('dang_xu_ly', 'Đang xử lý'),
        ('hoan_thanh', 'Đã giải quyết'),
        ('dong', 'Đã đóng')
    ], string="Trạng thái", default='moi', tracking=True)

    noi_dung = fields.Html(string="Nội dung yêu cầu")
    ket_qua_xu_ly = fields.Text(string="Kết quả xử lý", tracking=True)

    # --- ĐIỂM QUAN TRỌNG 3: Hàm tự động bắn thông báo khi gán nhân viên ---
    def write(self, vals):
        # Thực hiện việc lưu dữ liệu vào database trước
        res = super(HoTroKhachHang, self).write(vals)
        
        # Kiểm tra nếu trong lần lưu này có thay đổi (gán) nhân viên mới
        if 'nhan_vien_id' in vals and vals.get('nhan_vien_id'):
            for rec in self:
                # Truy xuất từ Nhân viên -> User hệ thống -> Partner ID để lấy định danh thông báo
                if rec.nhan_vien_id.tai_khoan_id:
                    p_id = rec.nhan_vien_id.tai_khoan_id.partner_id.id
                    
                    # Lấy nhãn (text) của mức độ ưu tiên để đưa vào nội dung tin nhắn
                    priority_label = dict(self._fields['muc_do_uu_tien'].selection).get(rec.muc_do_uu_tien)
                    
                    # Gửi thông báo trực tiếp vào hộp thư Inbox của nhân viên được gán
                    rec.message_post(
                        body=f"""
                            <div style="font-family: Arial, sans-serif;">
                                <p>🔔 <b>Bạn có nhiệm vụ hỗ trợ mới!</b></p>
                                <ul>
                                    <li><b>Tiêu đề:</b> {rec.tieu_de}</li>
                                    <li><b>Khách hàng:</b> {rec.khach_hang_id.name}</li>
                                    <li><b>Mức độ ưu tiên:</b> {priority_label}</li>
                                </ul>
                                <p>Vui lòng kiểm tra và xử lý kịp thời.</p>
                            </div>
                        """,
                        subject=f"Phân công hỗ trợ: {rec.tieu_de}",
                        partner_ids=[p_id] # "Tag" nhân viên vào danh sách nhận tin
                    )
        return res

    @api.model
    def create(self, vals):
        # Khi tạo mới, nếu có gán nhân viên luôn thì cũng nên bắn thông báo
        rec = super(HoTroKhachHang, self).create(vals)
        if rec.nhan_vien_id:
            # Tận dụng lại logic thông báo ở hàm write nếu cần thiết
            rec.write({'nhan_vien_id': rec.nhan_vien_id.id})
        return rec
# # -*- coding: utf-8 -*-
# from odoo import fields, models, api

# class HoTroKhachHang(models.Model):
#     _name = "ho_tro_khach_hang"
#     _description = "Hỗ trợ khách hàng"
#     _rec_name = 'tieu_de'

#     tieu_de = fields.Char(string="Tiêu đề yêu cầu", required=True)
#     khach_hang_id = fields.Many2one('khach_hang', string="Khách hàng", required=True)
    
#     # Liên kết với nhân viên phụ trách giải quyết
#     nhan_vien_id = fields.Many2one('nhan_vien', string="Nhân viên xử lý")
    
#     ngay_tiep_nhan = fields.Datetime(string="Ngày tiếp nhận", default=fields.Datetime.now)
#     ngay_hoan_thanh = fields.Datetime(string="Ngày hoàn thành")
    
#     muc_do_uu_tien = fields.Selection([
#         ('0', 'Thấp'),
#         ('1', 'Trung bình'),
#         ('2', 'Cao'),
#         ('3', 'Khẩn cấp')
#     ], string="Mức độ ưu tiên", default='1')
    
#     trang_thai = fields.Selection([
#         ('moi', 'Mới tiếp nhận'),
#         ('dang_xu_ly', 'Đang xử lý'),
#         ('hoan_thanh', 'Đã giải quyết'),
#         ('dong', 'Đã đóng')
#     ], string="Trạng thái", default='moi')

#     noi_dung = fields.Html(string="Nội dung yêu cầu")
#     ket_qua_xu_ly = fields.Text(string="Kết quả xử lý")

#     @api.model
#     def create(self, vals):
#         # Tự động chuyển trạng thái khách hàng hoặc thực hiện logic nếu cần
#         return super(HoTroKhachHang, self).create(vals)