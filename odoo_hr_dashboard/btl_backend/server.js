const express = require('express');
const cors = require('cors');
const xmlrpc = require('xmlrpc');
const fetch = (...args) => import('node-fetch').then(({default: fetch}) => fetch(...args));

const chatMemory = [];
const MAX_MEMORY = 6;

const app = express();
app.use(cors({ origin: '*' }));
app.use(express.json());

// --- CẤU HÌNH ODOO ---
const odooConfig = {
    host: 'localhost',
    port: 8069,
    db: 'btl_sach_cuoi_cung',
    username: 'admin',
    password: 'admin'
};

// Cấu hình API Gemini
const API_KEY = "AIzaSyAbjulNsVJ_67ANKeNPocqQp6EXGjHEOYQ";
const MODEL_NAME = "gemini-2.5-flash";

// --- HÀM KẾT NỐI ODOO (XML-RPC) ---
const callOdoo = (model, method, args) => {
    return new Promise((resolve, reject) => {
        const common = xmlrpc.createClient({ host: odooConfig.host, port: odooConfig.port, path: '/xmlrpc/2/common' });
        
        common.methodCall('login', [odooConfig.db, odooConfig.username, odooConfig.password], (err, uid) => {
            if (err) return reject("Lỗi Login Odoo: " + err.message);
            if (!uid) return reject("Sai tài khoản hoặc mật khẩu Odoo!");

            const models = xmlrpc.createClient({ host: odooConfig.host, port: odooConfig.port, path: '/xmlrpc/2/object' });
            models.methodCall('execute_kw', [odooConfig.db, uid, odooConfig.password, model, method, args], (err, res) => {
                if (err) return reject("Lỗi truy vấn Odoo: " + err.message);
                resolve(res);
            });
        });
    });
};

// --- API LẤY DANH SÁCH NHÂN VIÊN CHO SEARCH BAR ---
app.get('/api/employees', async (req, res) => {
    try {
        const employees = await callOdoo('nhan_vien', 'search_read', [[['trang_thai', '=', 'dang_lam']], ['ho_va_ten']]);
        res.json(employees.map(e => e.ho_va_ten));
    } catch (error) {
        res.json([]);
    }
});

// --- API DASHBOARD CHIẾN LƯỢC ---
app.get('/api/dashboard-extended', async (req, res) => {
    try {
        const { employeeName, date } = req.query; // Thêm biến date

        const [docs, customers, contracts] = await Promise.all([
            callOdoo('quan_ly_van_ban', 'search_read', [[], ['trang_thai']]),
            callOdoo('khach_hang', 'search_read', [[], ['ma_khach_hang', 'nhan_vien_id', 'giai_doan', 'ngay_nhan_lead']]),
            callOdoo('hop_dong', 'search_read', [[], ['nhan_vien_id', 'trang_thai', 'create_date']])
        ]);

        const leadStages = ['tiep_can', 'ket_noi', 'dam_phan'];
        
        let allRealLeads = customers.filter(c => 
            c.ma_khach_hang && 
            c.ma_khach_hang.startsWith('KH') &&
            c.nhan_vien_id !== false &&
            leadStages.includes(c.giai_doan)
        );

        let allSignedContracts = contracts.filter(con => 
            con.trang_thai === 'hoan_thanh' || con.trang_thai === 'Hoàn thành'
        );

        // --- LỌC THEO THỜI GIAN (NẾU CÓ) ---
        if (date && date.trim() !== "") {
            const [year, month] = date.split('-');
            const startDate = new Date(year, month - 1, 1);
            const endDate = new Date(year, month, 0, 23, 59, 59);

            allRealLeads = allRealLeads.filter(c => {
                if (!c.ngay_nhan_lead) return false;
                const leadDate = new Date(c.ngay_nhan_lead);
                return leadDate >= startDate && leadDate <= endDate;
            });

            allSignedContracts = allSignedContracts.filter(con => {
                if (!con.create_date) return false;
                const contractDate = new Date(con.create_date);
                return contractDate >= startDate && contractDate <= endDate;
            });
        }

        let chartLeads = [...allRealLeads];
        let chartSales = [...allSignedContracts];

        if (employeeName && employeeName.trim() !== "") {
            chartLeads = chartLeads.filter(c => c.nhan_vien_id && c.nhan_vien_id[1] === employeeName);
            chartSales = chartSales.filter(s => s.nhan_vien_id && s.nhan_vien_id[1] === employeeName);
        }

        const kpi = {};
        chartLeads.forEach(c => {
            const name = c.nhan_vien_id[1];
            if (!kpi[name]) kpi[name] = { name, leads: 0, sales: 0 };
            kpi[name].leads += 1;
        });

        chartSales.forEach(con => {
            const name = con.nhan_vien_id[1];
            if (!kpi[name]) kpi[name] = { name, leads: 0, sales: 0 };
            kpi[name].sales += 1;
        });

        res.json({
            totalLeads: allRealLeads.length,
            successfulSales: allSignedContracts.length,
            pendingDocsCount: docs.filter(d => d.trang_thai === 'cho_duyet').length,
            kpiData: Object.values(kpi),
            conversionRate: allRealLeads.length > 0 
                ? parseFloat(((allSignedContracts.length / allRealLeads.length) * 100).toFixed(1)) 
                : 0
        });

        console.log(`✅ Dashboard: ${allRealLeads.length} Leads, ${allSignedContracts.length} Sales. Filter: ${employeeName || 'All'} | Date: ${date || 'All'}`);

    } catch (error) {
        console.error("❌ Lỗi API Dashboard:", error.message);
        res.status(500).json({ error: error.message });
    }
});

// --- ✨ API BIỂU ĐỒ CHUYỂN ĐỔI CÓ BỘ LỌC THỜI GIAN ---
app.get('/api/conversion-chart', async (req, res) => {
    try {
        const { month, year } = req.query;
        
        console.log(`📊 Conversion Chart - Filter: ${month ? `Tháng ${month}` : 'Tất cả'} / ${year || 'Tất cả năm'}`);

        // Lấy TẤT CẢ khách hàng từ model khach_hang (GIỐNG API DASHBOARD-EXTENDED)
        let allCustomers = await callOdoo('khach_hang', 'search_read', [
            [],
            ['ma_khach_hang', 'giai_doan', 'nhan_vien_id', 'ngay_nhan_lead']
        ]);

        // Lọc theo thời gian nếu có
        if (month && year) {
            const startDate = new Date(year, month - 1, 1);
            const endDate = new Date(year, month, 0, 23, 59, 59);
            
            allCustomers = allCustomers.filter(c => {
                if (!c.ngay_nhan_lead) return false;
                const leadDate = new Date(c.ngay_nhan_lead);
                return leadDate >= startDate && leadDate <= endDate;
            });
        } else if (year) {
            const startDate = new Date(year, 0, 1);
            const endDate = new Date(year, 11, 31, 23, 59, 59);
            
            allCustomers = allCustomers.filter(c => {
                if (!c.ngay_nhan_lead) return false;
                const leadDate = new Date(c.ngay_nhan_lead);
                return leadDate >= startDate && leadDate <= endDate;
            });
        }

        // LOGIC GIỐNG API DASHBOARD-EXTENDED
        const leadStages = ['tiep_can', 'ket_noi', 'dam_phan'];
        const customerStages = ['ky_hop_dong', 'thanh_cong'];

        // Lấy Lead (GIỐNG HỆT DASHBOARD)
        const allLeads = allCustomers.filter(c => 
            c.ma_khach_hang && 
            c.ma_khach_hang.startsWith('KH') &&
            c.nhan_vien_id !== false &&
            leadStages.includes(c.giai_doan)
        );

        // Lấy Khách hàng đã chuyển đổi
        const allConvertedCustomers = allCustomers.filter(c => 
            c.ma_khach_hang && 
            c.ma_khach_hang.startsWith('KH') &&
            customerStages.includes(c.giai_doan)
        );

        const totalLeads = allLeads.length;
        const totalCustomers = allConvertedCustomers.length;
        
        // Tính tỷ lệ chuyển đổi
        const conversionRate = totalLeads > 0 
            ? parseFloat(((totalCustomers / totalLeads) * 100).toFixed(1))
            : 0;

        res.json({
            leads: totalLeads,
            customers: totalCustomers,
            conversionRate: conversionRate,
            filterInfo: {
                month: month || 'Tất cả',
                year: year || 'Tất cả',
                totalRecords: totalLeads + totalCustomers
            }
        });

        console.log(`✅ Conversion: ${totalLeads} Leads → ${totalCustomers} Customers (${conversionRate}%)`);

    } catch (error) {
        console.error("❌ Lỗi API Conversion Chart:", error.message);
        res.status(500).json({ error: error.message });
    }
});

// --- ✨ API LẤY DANH SÁCH NĂM CÓ DỮ LIỆU ---
app.get('/api/available-periods', async (req, res) => {
    try {
        const allCustomers = await callOdoo('khach_hang', 'search_read', [
            [],
            ['ngay_nhan_lead']
        ]);

        const periods = new Set();
        allCustomers.forEach(customer => {
            if (customer.ngay_nhan_lead) {
                const date = new Date(customer.ngay_nhan_lead);
                const period = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
                periods.add(period);
            }
        });

        const sortedPeriods = Array.from(periods).sort().reverse();
        
        res.json({
            periods: sortedPeriods,
            years: [...new Set(sortedPeriods.map(p => p.split('-')[0]))].sort().reverse()
        });

    } catch (error) {
        console.error("❌ Lỗi API Available Periods:", error.message);
        res.status(500).json({ error: error.message });
    }
});

// --- API AI THÔNG MINH (CÓ ROUTER) ---
app.post('/api/ai-chat', async (req, res) => {
    const { message } = req.body;
    const lowerMsg = message.toLowerCase();

    console.log(`🤖 AI Router nhận: ${message}`);

    // HỎI DASHBOARD
    if (
        lowerMsg.includes('bao nhiêu lead') ||
        lowerMsg.includes('bao nhiêu khách') ||
        lowerMsg.includes('dashboard') ||
        lowerMsg.includes('doanh số')
    ) {
        try {
            const customers = await callOdoo('khach_hang', 'search_read', [[], ['ma_khach_hang']]);
            const totalLeads = customers.filter(c => c.ma_khach_hang?.startsWith('KH')).length;

            return res.json({
                reply: `Hiện tại trong hệ thống đang có ${totalLeads} lead (khách hàng tiềm năng).`
            });
        } catch (e) {
            return res.json({ reply: "Không thể lấy dữ liệu dashboard lúc này." });
        }
    }

    // HỎI THỜI TIẾT
    if (lowerMsg.includes('thời tiết')) {
        return res.json({
            reply: "Hôm nay thời tiết nhìn chung khá dễ chịu, bạn nên mang theo áo khoác nhẹ nếu ra ngoài."
        });
    }

    // KIẾN THỨC CHUNG → GEMINI
    const API_URL = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL_NAME}:generateContent?key=${API_KEY}`;

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contents: [{
                    parts: [{
                        text: `
Bạn là trợ lý AI thông minh như ChatGPT.
Hãy trả lời trực tiếp, tự tin, KHÔNG nói các câu kiểu "tôi không có khả năng".
Nếu thiếu dữ liệu thực tế, hãy trả lời theo kiến thức phổ thông.

Câu hỏi: ${message}
                        `
                    }]
                }]
            })
        });

        const data = await response.json();
        const aiText = data?.candidates?.[0]?.content?.parts?.[0]?.text 
            || "Mình chưa trả lời được câu này.";

        res.json({ reply: aiText });

    } catch (error) {
        res.status(500).json({ reply: "Lỗi kết nối AI." });
    }
});

// --- KHỞI CHẠY SERVER ---
const PORT = 5000;
app.listen(PORT, '0.0.0.0', () => {
    console.log('===========================================');
    console.log(`🚀 SERVER MIDDLEWARE ĐANG CHẠY TẠI PORT ${PORT}`);
    console.log(`📡 KẾT NỐI ODOO: ${odooConfig.host}:${odooConfig.port}`);
    console.log('📊 API Conversion Chart: /api/conversion-chart?month=1&year=2025');
    console.log('📅 API Available Periods: /api/available-periods');
    console.log('===========================================');
});

