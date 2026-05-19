from flask import render_template, request, redirect, url_for, session, abort, jsonify, flash, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename

from app import dao, app, login, db, utils, socketio
from app.models import DanhMucMonAn, MonAn, NhaHang, EnumRole, DonHang, ChiTietDonHang, EnumStatus, DanhGia, ThongBao, GioHang, ChiTietGioHang
import cloudinary.uploader
from collections import Counter
import requests

from app.utils import send_gmail

from flask import render_template, make_response
from xhtml2pdf import pisa
import io, os

from flask_socketio import join_room

from app.admin_view import *

@socketio.on('join')
def handle_join(data):
    room = data.get("room")
    if room:
        join_room(room)
        print(f"Client joined room: {room}")

@app.route('/xuat-bill/<int:id>')
def xuat_bill(id):
    don_hang = DonHang.query.get_or_404(id)

    html = render_template('restaurent/bill_template.html', dh=don_hang)

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=pdf_buffer)

    if pisa_status.err:
        return f"Lỗi khi tạo PDF: {pisa_status.err}", 500

    pdf_buffer.seek(0)
    response = make_response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=hoadon_{don_hang.id}.pdf'
    return response


def lay_hoac_tao_gio_hang(user_id, nha_hang_id):
    gio_hang = GioHang.query.filter_by(userId=user_id, nhaHangId=nha_hang_id).order_by(GioHang.time.desc()).first()

    if gio_hang is None:
        gio_hang = GioHang(userId=user_id, nhaHangId=nha_hang_id)
        db.session.add(gio_hang)
        db.session.commit()

    return gio_hang


def xoa_gio_hang_neu_trong(gio_hang):
    if not ChiTietGioHang.query.filter_by(idGioHang=gio_hang.id).first():
        db.session.delete(gio_hang)
        db.session.commit()


def tong_tien_gio_hang(gio_hang):
    return sum((chi_tiet.mon_an.gia or 0) * chi_tiet.soLuong for chi_tiet in gio_hang.chi_tiet_gio_hang)


def payment_status_for_method(phuong_thuc):
    if phuong_thuc == 'cod':
        return 'PENDING'
    return 'COMPLETED'


def tao_don_hang_tu_gio_hang(gio_hang, khach_hang, phuong_thuc, paypal_order_id=None):
    chi_tiets = ChiTietGioHang.query.filter_by(idGioHang=gio_hang.id).all()
    if not chi_tiets:
        return None

    tong_tien = tong_tien_gio_hang(gio_hang)
    don_hang = DonHang(
        idKH=khach_hang.id,
        idNhaHang=gio_hang.nhaHangId,
        tongGia=tong_tien,
        trangThai=EnumStatus.cho,
        paymentMethod=phuong_thuc,
        paymentStatus=payment_status_for_method(phuong_thuc),
        paypalOrderId=paypal_order_id
    )
    db.session.add(don_hang)
    db.session.flush()

    for chi_tiet in chi_tiets:
        db.session.add(ChiTietDonHang(
            idDH=don_hang.id,
            idMonAn=chi_tiet.idMonAn,
            soLuong=chi_tiet.soLuong
        ))

    noi_dung_tb = f"Don hang moi #{don_hang.id} tu {khach_hang.name} ({phuong_thuc})"
    gui_thong_bao_nguoi_dung(
        gio_hang.nhaHangId,
        noi_dung_tb,
        url_for('chi_tiet_don_hang', id=don_hang.id)
    )

    for chi_tiet in chi_tiets:
        db.session.delete(chi_tiet)
    db.session.delete(gio_hang)
    db.session.commit()

    return don_hang


def paypal_credentials():
    client_id = os.getenv("PAYPAL_CLIENT_ID", "").strip()
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()
    base_url = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com").strip()
    currency = os.getenv("PAYPAL_CURRENCY", "USD").strip().upper()
    vnd_rate = float(os.getenv("PAYPAL_VND_RATE", "25000"))
    return client_id, client_secret, base_url, currency, vnd_rate


def paypal_enabled():
    client_id, client_secret, _, _, _ = paypal_credentials()
    return bool(client_id and client_secret)


def paypal_amount_from_vnd(vnd_amount):
    _, _, _, currency, vnd_rate = paypal_credentials()
    if currency == "USD":
        return f"{round(float(vnd_amount) / vnd_rate, 2):.2f}"
    return f"{round(float(vnd_amount), 2):.2f}"


def paypal_access_token():
    client_id, client_secret, base_url, _, _ = paypal_credentials()
    response = requests.post(
        f"{base_url}/v1/oauth2/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        timeout=30
    )
    response.raise_for_status()
    return response.json()["access_token"]


def gui_thong_bao_nguoi_dung(user_id, noi_dung, url):
    thong_bao = ThongBao(
        noi_dung=noi_dung,
        user_id=user_id,
        url=url
    )
    db.session.add(thong_bao)
    db.session.flush()

    socketio.emit(
        "thong_bao_moi",
        {"noi_dung": noi_dung, "url": url},
        room=f"user_{user_id}"
    )

    return thong_bao


def cap_nhat_trang_thai_don(don_hang, trang_thai_moi, ghi_chu_huy=None):
    don_hang.trangThai = trang_thai_moi
    db.session.commit()

    noi_dung = f"Don hang #{don_hang.id} da duoc cap nhat: {don_hang.trangThai.value}"
    if trang_thai_moi == EnumStatus.daHuy and ghi_chu_huy:
        noi_dung += f". Ly do: {ghi_chu_huy}"

    gui_thong_bao_nguoi_dung(
        don_hang.idKH,
        noi_dung,
        url_for('chi_tiet_don_hang_khach_hang', id=don_hang.id)
    )
    db.session.commit()


def goi_y_mon_an_cho_khach(user):
    if not user.is_authenticated or user.role != EnumRole.khachHang:
        return []

    dem_danh_muc = Counter()
    mon_da_dat = set()

    don_hangs = DonHang.query.filter_by(idKH=user.id).all()
    for don_hang in don_hangs:
        for chi_tiet in don_hang.chi_tiet_don_hang:
            mon_da_dat.add(chi_tiet.idMonAn)
            if chi_tiet.mon_an and chi_tiet.mon_an.idDanhMuc:
                dem_danh_muc[chi_tiet.mon_an.idDanhMuc] += chi_tiet.soLuong

    query = MonAn.query.filter(MonAn.tinhTrang == True)

    gio = datetime.now().hour
    if gio < 10:
        query = query.filter(
            (DanhMucMonAn.id == MonAn.idDanhMuc) &
            (DanhMucMonAn.tenDanhMuc.in_(["Thức uống", "Khai vị"]))
        )
    elif gio >= 20:
        query = query.filter(
            (DanhMucMonAn.id == MonAn.idDanhMuc) &
            (DanhMucMonAn.tenDanhMuc.in_(["Món chính", "Lẩu", "Tráng miệng"]))
        )

    if dem_danh_muc:
        danh_muc_uu_tien = [item[0] for item in dem_danh_muc.most_common(3)]
        foods = query.filter(MonAn.idDanhMuc.in_(danh_muc_uu_tien), ~MonAn.id.in_(mon_da_dat)).limit(4).all()
        if foods:
            return foods

    return query.limit(4).all()


def goi_y_mon_di_kem(mon_an):
    dem_mon = Counter()

    for chi_tiet in mon_an.chi_tiet_don_hang:
        for mon_kem in chi_tiet.don_hang.chi_tiet_don_hang:
            if mon_kem.idMonAn != mon_an.id:
                dem_mon[mon_kem.idMonAn] += mon_kem.soLuong

    if dem_mon:
        ids = [item[0] for item in dem_mon.most_common(4)]
        mon_goi_y = MonAn.query.filter(MonAn.id.in_(ids)).all()
        mon_goi_y.sort(key=lambda item: ids.index(item.id))
        return mon_goi_y

    return MonAn.query.filter(
        MonAn.idNhaHang == mon_an.idNhaHang,
        MonAn.id != mon_an.id,
        MonAn.tinhTrang == True
    ).limit(4).all()


def phan_tich_danh_gia_mon(mon_an):
    ket_qua = {"tich_cuc": 0, "trung_tinh": 0, "tieu_cuc": 0}
    tu_tich_cuc = ["ngon", "tot", "tuyet", "rat thich", "hai long"]
    tu_tieu_cuc = ["do", "te", "man", "nhat", "lau", "khong ngon", "that vong"]

    for danh_gia in mon_an.danh_gia:
        noi_dung = (danh_gia.content or "").lower()
        if danh_gia.sao >= 4 or any(tu in noi_dung for tu in tu_tich_cuc):
            ket_qua["tich_cuc"] += 1
        elif danh_gia.sao <= 2 or any(tu in noi_dung for tu in tu_tieu_cuc):
            ket_qua["tieu_cuc"] += 1
        else:
            ket_qua["trung_tinh"] += 1

    tong = sum(ket_qua.values())
    ket_qua["tong"] = tong
    ket_qua["trung_binh_sao"] = round(sum(dg.sao for dg in mon_an.danh_gia) / tong, 1) if tong else 0
    return ket_qua
@app.route('/')
def index():
    kw = request.args.get('kw', '')
    category_id = request.args.get('category_id', type=int)
    nha_hang_id = request.args.get('nha_hang_id', type=int)
    min_gia = request.args.get('min_gia', type=float)
    max_gia = request.args.get('max_gia', type=float)
    con_mon = request.args.get('con_mon') == '1'
    cates = dao.load_categories()
    nha_hangs = dao.load_nha_hang()
    foods = dao.load_foods(
        keyword=kw,
        category_id=category_id,
        nha_hang_id=nha_hang_id,
        min_gia=min_gia,
        max_gia=max_gia,
        con_mon=con_mon
    )
    goi_y_mon_an = goi_y_mon_an_cho_khach(current_user) if current_user.is_authenticated else []
    return render_template(
        'index.html',
        categories=cates,
        foods=foods,
        kw=kw,
        goi_y_mon_an=goi_y_mon_an,
        nha_hangs=nha_hangs,
        selected_category_id=category_id,
        selected_nha_hang_id=nha_hang_id,
        min_gia=min_gia,
        max_gia=max_gia,
        con_mon=con_mon
    )
@app.route('/nha-hang', methods=['GET'])
def danh_sach_nha_hang():
    kw = request.args.get('kw', '')
    nha_hangs = dao.load_nha_hang(keyword=kw)  # hàm đã có sẵn
    return render_template('nha_hang_list.html', nha_hangs=nha_hangs, kw=kw)

@app.route('/danh-muc/<int:category_id>')
def food_by_category(category_id):
    categories = DanhMucMonAn.query.all()
    foods = MonAn.query.filter_by(idDanhMuc=category_id).all()
    return render_template('index.html', categories=categories, foods=foods)

@app.route("/login", methods=['get', 'post'])
def login_process():
    if request.method.__eq__('POST'):
        username = request.form.get('username')
        password = request.form.get('password')

        u = dao.auth_user(username=username, password=password)
        if u:
            login_user(u)

            next = request.args.get('next')
            return redirect(next if next else '/')

    return render_template('login.html')
@app.route("/logout")
def logout_process():
    logout_user()
    return redirect('/login')

@app.route("/register", methods=['get', 'post'])
def register_process():
    err_msg = None
    if request.method.__eq__('POST'):
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if password == confirm:
            email = request.form.get('email')
            if not email:
                err_msg = 'Email là bắt buộc!'
            else:
                data = request.form.copy()
                del data['confirm']

                avt = request.files.get('avt')
                dao.add_user(avt=avt, **data)
                return redirect('/login')
        else:
            err_msg = 'Mật khẩu KHÔNG khớp!'

    return render_template('register.html', err_msg=err_msg)

@app.route("/nha-hang/<int:nha_hang_id>")
def chi_tiet_nha_hang(nha_hang_id):
    nha_hang = NhaHang.query.get_or_404(nha_hang_id)
    danh_sach_mon = MonAn.query.filter_by(idNhaHang=nha_hang.id).all()

    return render_template("restaurentDetail.html", nha_hang=nha_hang, foods=danh_sach_mon)

@app.route('/api/cap-nhat-mon/<int:mon_an_id>', methods=['POST'])
@login_required
def api_cap_nhat_mon(mon_an_id):
    data = request.get_json()
    tinh_trang_moi_raw = data.get('tinh_trang_moi')


    tinh_trang_moi = tinh_trang_moi_raw in ['true', 'True', True, 1, '1']

    mon = db.session.get(MonAn, mon_an_id)
    if not mon:
        return jsonify({'status': 'error', 'message': 'Món không tồn tại'}), 404


    if mon.nha_hang.id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Không có quyền'}), 403


    mon.tinhTrang = tinh_trang_moi
    db.session.commit()

    return jsonify({'status': 'success', 'tinh_trang': mon.tinhTrang})

@app.route('/mon-an/<int:food_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_food(food_id):
    mon = MonAn.query.get_or_404(food_id)

    if current_user.role != EnumRole.nhaHang or mon.idNhaHang != current_user.id:
        abort(403)

    if request.method == 'POST':
        mon.name = request.form['name']
        mon.gia = request.form['gia']
        mon.chiTietMon = request.form['chiTietMon']
        mon.tinhTrang = request.form.get('tinhTrang') == 'on'

        img_file = request.files.get('img')
        if img_file and img_file.filename != '':
            # Upload lên Cloudinary
            res = cloudinary.uploader.upload(img_file)
            mon.img = res['secure_url']

        db.session.commit()
        return redirect(url_for('chi_tiet_nha_hang', nha_hang_id=current_user.id))

    return render_template('restaurent/edit_food.html', food=mon)

@app.route("/nha-hang/don-hang")
@login_required
def quan_ly_don_hang():
    if current_user.role != EnumRole.nhaHang:
        return "Bạn không có quyền truy cập", 403


    trang_thai = request.args.get("trang_thai")  # VD: 'daXacNhan'
    sap_xep = request.args.get("sap_xep", "desc")  # asc hoặc desc

    query = DonHang.query.filter_by(idNhaHang=current_user.id)

    if trang_thai:
        from app.models import EnumStatus
        try:
            query = query.filter(DonHang.trangThai == EnumStatus[trang_thai])
        except KeyError:
            pass

    if sap_xep == "asc":
        query = query.order_by(DonHang.thoiGian.asc())
    else:
        query = query.order_by(DonHang.thoiGian.desc())

    don_hang = query.all()

    return render_template(
        "restaurent/quan_ly_don_hang.html",
        don_hang=don_hang,
        trang_thai_hien_tai=trang_thai,
        sap_xep_hien_tai=sap_xep
    )

@app.route('/nha-hang/don-hang/<int:id>', methods=['GET', 'POST'])
@login_required
def chi_tiet_don_hang(id):
    if current_user.role != EnumRole.nhaHang:
        return "Bạn không có quyền truy cập", 403

    don_hang = DonHang.query.get_or_404(id)
    if don_hang.idNhaHang != current_user.id:
        return "Không có quyền xem đơn hàng này", 403

    chi_tiet = ChiTietDonHang.query.filter_by(idDH=id).all()

    if request.method == 'POST':
        new_status = request.form.get('trangThai')
        note = request.form.get('noiDungHuy', '').strip()

        # Kiểm tra nếu hủy mà không nhập lý do
        if new_status == 'daHuy' and not note:
            flash("Phải nhập lý do khi hủy đơn hàng!", "danger")
        else:
            try:
                cap_nhat_trang_thai_don(don_hang, EnumStatus[new_status], note)

                # Gửi email
                subject = f"Đơn hàng #{don_hang.id} - Trạng thái mới: {don_hang.trangThai.value}"
                content = f"""
                    <p>Xin chào {don_hang.khach_hang.name},</p>
                    <p>Đơn hàng của bạn đã được cập nhật trạng thái: <strong>{don_hang.trangThai.value}</strong></p>
                """

                if new_status == 'daHuy' and note:
                    content += f"<p><strong>Lý do hủy:</strong> {note}</p>"

                send_gmail(don_hang.khach_hang.email, subject, content)
                flash("Cập nhật và gửi email thành công!", "success")

            except Exception as e:
                print("Lỗi cập nhật trạng thái:", e)
                flash("Có lỗi xảy ra khi cập nhật đơn hàng!", "danger")

            return redirect(url_for('chi_tiet_don_hang', id=id))

    return render_template('restaurent/chi_tiet_don_hang.html', don_hang=don_hang, chi_tiet=chi_tiet)

@app.route('/register-nhahang', methods=['get', 'post'])
def register_nhahang():
    err_msg = None
    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm')
        if password == confirm:
            data = request.form.copy()
            del data['confirm']
            avt = request.files.get('avt')

            try:
                dao.add_nha_hang(avt=avt, **data)
                return redirect('/login')
            except Exception as e:
                err_msg = f"Lỗi: {str(e)}"
        else:
            err_msg = "Mật khẩu không khớp!"

    return render_template('register_nhahang.html', err_msg=err_msg)



from flask_socketio import emit

@app.route('/mon-an/<int:id>', methods=['GET', 'POST'])
def chi_tiet_mon_an(id):
    mon_an = MonAn.query.get_or_404(id)

    if request.method == 'POST':
        if not current_user.is_authenticated or current_user.role != EnumRole.khachHang:
            flash("Bạn cần đăng nhập bằng tài khoản khách hàng để đánh giá.", "warning")
            return redirect(url_for('login_process'))

        sao_raw = request.form.get('sao')
        content = request.form.get('content', '').strip()

        if not sao_raw:
            flash("Vui lÃ²ng chá»n sá»‘ sao Ä‘á»ƒ gá»­i Ä‘Ã¡nh giÃ¡.", "warning")
            return redirect(url_for('chi_tiet_mon_an', id=mon_an.id))

        sao = int(sao_raw)

        danh_gia = DanhGia(
            content=content,
            sao=sao,
            user_id=current_user.id,
            mon_an_id=mon_an.id
        )
        db.session.add(danh_gia)
        db.session.commit()

        nha_hang_id = mon_an.idNhaHang
        noi_dung_tb = f"{current_user.name} đã đánh giá món: {mon_an.name} ⭐ {sao}/5"
        url = url_for('chi_tiet_mon_an', id=mon_an.id)

        thong_bao = ThongBao(
            noi_dung=noi_dung_tb,
            user_id=nha_hang_id,
            mon_an_id=mon_an.id,
            url=url
        )
        db.session.add(thong_bao)
        db.session.commit()

        socketio.emit(
            "thong_bao_moi",
            {"noi_dung": noi_dung_tb,
             "url": url
             },
            room=f"user_{nha_hang_id}"
        )

        flash("Đánh giá đã được gửi!", "success")
        return redirect(url_for('chi_tiet_mon_an', id=mon_an.id))

    mon_goi_y = goi_y_mon_di_kem(mon_an)
    thong_ke_danh_gia = phan_tich_danh_gia_mon(mon_an)
    return render_template('monAnDetail.html', mon_an=mon_an, mon_goi_y=mon_goi_y, thong_ke_danh_gia=thong_ke_danh_gia)


@app.route('/gio-hang/them/<int:id>', methods=['POST'])
@login_required
def them_vao_gio(id):
    if current_user.role != EnumRole.khachHang:
        abort(403)

    so_luong = request.form.get('soLuong', type=int, default=1)
    if so_luong is None or so_luong < 1:
        flash("So luong khong hop le.", "warning")
        return redirect(url_for('chi_tiet_mon_an', id=id))

    mon_an = MonAn.query.get_or_404(id)
    gio_hang = lay_hoac_tao_gio_hang(current_user.id, mon_an.idNhaHang)
    chi_tiet = ChiTietGioHang.query.filter_by(idGioHang=gio_hang.id, idMonAn=mon_an.id).first()

    if chi_tiet:
        chi_tiet.soLuong += so_luong
    else:
        chi_tiet = ChiTietGioHang(idMonAn=mon_an.id, idGioHang=gio_hang.id, soLuong=so_luong)
        db.session.add(chi_tiet)

    db.session.commit()

    flash("Da them mon vao gio hang.", "success")
    return redirect(url_for('xem_gio_hang'))


@app.route('/gio-hang')
@login_required
def xem_gio_hang():
    if current_user.role != EnumRole.khachHang:
        abort(403)

    gio_hang_data = []
    tong_tien = 0
    tong_mon = 0

    gio_hangs = GioHang.query.filter_by(userId=current_user.id).order_by(GioHang.time.desc()).all()

    for gio_hang in gio_hangs:
        chi_tiets = ChiTietGioHang.query.filter_by(idGioHang=gio_hang.id).all()
        if not chi_tiets:
            continue

        items = []
        tong_theo_nha_hang = 0

        for chi_tiet in chi_tiets:
            thanh_tien = (chi_tiet.mon_an.gia or 0) * chi_tiet.soLuong
            tong_theo_nha_hang += thanh_tien
            tong_tien += thanh_tien
            tong_mon += chi_tiet.soLuong
            items.append({
                'chi_tiet': chi_tiet,
                'mon_an': chi_tiet.mon_an,
                'thanh_tien': thanh_tien
            })

        gio_hang_data.append({
            'gio_hang': gio_hang,
            'nha_hang': gio_hang.nha_hang,
            'cart_items': items,
            'tong_theo_nha_hang': tong_theo_nha_hang
        })

    return render_template('gio_hang.html', gio_hang_data=gio_hang_data, tong_tien=tong_tien, tong_mon=tong_mon)


@app.route('/gio-hang/<int:chi_tiet_id>/tang', methods=['POST'])
@login_required
def tang_so_luong_gio_hang(chi_tiet_id):
    if current_user.role != EnumRole.khachHang:
        abort(403)

    chi_tiet = ChiTietGioHang.query.get_or_404(chi_tiet_id)
    if chi_tiet.gio_hang.userId != current_user.id:
        abort(403)

    chi_tiet.soLuong += 1
    db.session.commit()

    return redirect(url_for('xem_gio_hang'))


@app.route('/gio-hang/<int:chi_tiet_id>/giam', methods=['POST'])
@login_required
def giam_so_luong_gio_hang(chi_tiet_id):
    if current_user.role != EnumRole.khachHang:
        abort(403)

    chi_tiet = ChiTietGioHang.query.get_or_404(chi_tiet_id)
    if chi_tiet.gio_hang.userId != current_user.id:
        abort(403)

    gio_hang = chi_tiet.gio_hang
    if chi_tiet.soLuong <= 1:
        db.session.delete(chi_tiet)
        db.session.commit()
        xoa_gio_hang_neu_trong(gio_hang)
    else:
        chi_tiet.soLuong -= 1
        db.session.commit()

    return redirect(url_for('xem_gio_hang'))


@app.route('/gio-hang/thanh-toan/<int:gio_hang_id>', methods=['GET', 'POST'])
@login_required
def thanh_toan_gio_hang(gio_hang_id):
    if current_user.role != EnumRole.khachHang:
        abort(403)

    gio_hang = GioHang.query.get_or_404(gio_hang_id)
    if gio_hang.userId != current_user.id:
        abort(403)

    chi_tiets = ChiTietGioHang.query.filter_by(idGioHang=gio_hang.id).all()
    if not chi_tiets:
        flash("Gio hang nay dang trong.", "warning")
        return redirect(url_for('xem_gio_hang'))

    tong_tien = tong_tien_gio_hang(gio_hang)

    if request.method == 'POST':
        phuong_thuc = request.form.get('phuong_thuc_thanh_toan', 'cod')
        if phuong_thuc == 'paypal':
            if not paypal_enabled():
                flash("Thieu PAYPAL_CLIENT_ID hoac PAYPAL_CLIENT_SECRET cho sandbox.", "warning")
                return redirect(url_for('thanh_toan_gio_hang', gio_hang_id=gio_hang.id))
            return redirect(url_for('paypal_checkout', gio_hang_id=gio_hang.id))

        don_hang = tao_don_hang_tu_gio_hang(gio_hang, current_user, phuong_thuc)
        if don_hang is None:
            flash("Gio hang nay dang trong.", "warning")
            return redirect(url_for('xem_gio_hang'))

        flash(f"Dat hang thanh cong. Phuong thuc thanh toan: {phuong_thuc}.", "success")
        return redirect(url_for('chi_tiet_don_hang_khach_hang', id=don_hang.id))

    return render_template(
        'thanh_toan.html',
        gio_hang=gio_hang,
        chi_tiets=chi_tiets,
        tong_tien=tong_tien,
        paypal_sandbox_ready=paypal_enabled()
    )


@app.route('/thanh-toan/paypal/<int:gio_hang_id>')
@login_required
def paypal_checkout(gio_hang_id):
    if current_user.role != EnumRole.khachHang:
        abort(403)

    gio_hang = GioHang.query.get_or_404(gio_hang_id)
    if gio_hang.userId != current_user.id:
        abort(403)

    chi_tiets = ChiTietGioHang.query.filter_by(idGioHang=gio_hang.id).all()
    if not chi_tiets:
        flash("Gio hang nay dang trong.", "warning")
        return redirect(url_for('xem_gio_hang'))

    tong_tien = tong_tien_gio_hang(gio_hang)
    client_id, _, _, currency, _ = paypal_credentials()
    paypal_amount = paypal_amount_from_vnd(tong_tien)
    return render_template(
        'paypal_checkout.html',
        gio_hang=gio_hang,
        chi_tiets=chi_tiets,
        tong_tien=tong_tien,
        paypal_client_id=client_id,
        paypal_currency=currency,
        paypal_amount=paypal_amount
    )


@app.route('/api/paypal/orders/<int:gio_hang_id>', methods=['POST'])
@login_required
def tao_paypal_order(gio_hang_id):
    if current_user.role != EnumRole.khachHang:
        return jsonify({"error": "Forbidden"}), 403

    gio_hang = GioHang.query.get_or_404(gio_hang_id)
    if gio_hang.userId != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    if not paypal_enabled():
        return jsonify({"error": "Missing PayPal sandbox credentials"}), 400

    tong_tien = tong_tien_gio_hang(gio_hang)
    amount_value = paypal_amount_from_vnd(tong_tien)
    _, _, base_url, currency, _ = paypal_credentials()
    try:
        access_token = paypal_access_token()
        response = requests.post(
            f"{base_url}/v2/checkout/orders",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            json={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": str(gio_hang.id),
                        "amount": {
                            "currency_code": currency,
                            "value": amount_value
                        }
                    }
                ]
            },
            timeout=30
        )
    except requests.RequestException as exc:
        return jsonify({"error": "PayPal request failed", "details": str(exc)}), 400

    if not response.ok:
        return jsonify({"error": "PayPal create order failed", "details": response.text}), 400

    order_data = response.json()
    return jsonify({"id": order_data.get("id")})


@app.route('/api/paypal/orders/<order_id>/capture', methods=['POST'])
@login_required
def capture_paypal_order(order_id):
    if current_user.role != EnumRole.khachHang:
        return jsonify({"error": "Forbidden"}), 403

    gio_hang_id = request.get_json(silent=True, force=False) or {}
    gio_hang_id = gio_hang_id.get("gio_hang_id")
    if not gio_hang_id:
        return jsonify({"error": "gio_hang_id is required"}), 400

    gio_hang = GioHang.query.get_or_404(gio_hang_id)
    if gio_hang.userId != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    _, _, base_url, _, _ = paypal_credentials()
    try:
        access_token = paypal_access_token()
        response = requests.post(
            f"{base_url}/v2/checkout/orders/{order_id}/capture",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            },
            timeout=30
        )
    except requests.RequestException as exc:
        return jsonify({"error": "PayPal request failed", "details": str(exc)}), 400

    if not response.ok:
        return jsonify({"error": "PayPal capture failed", "details": response.text}), 400

    capture_data = response.json()
    status = capture_data.get("status")
    if status != "COMPLETED":
        return jsonify({"error": "Payment not completed", "details": capture_data}), 400

    don_hang = tao_don_hang_tu_gio_hang(gio_hang, current_user, 'paypal_sandbox', paypal_order_id=order_id)
    if don_hang is None:
        return jsonify({"error": "Cart is empty"}), 400

    return jsonify({
        "success": True,
        "redirect_url": url_for('chi_tiet_don_hang_khach_hang', id=don_hang.id)
    })


@app.route('/don-hang-cua-toi')
@login_required
def don_hang_cua_toi():
    if current_user.role != EnumRole.khachHang:
        abort(403)

    don_hangs = DonHang.query.filter_by(idKH=current_user.id).order_by(DonHang.thoiGian.desc()).all()
    return render_template('don_hang_cua_toi.html', don_hangs=don_hangs)


@app.route('/don-hang/<int:id>')
@login_required
def chi_tiet_don_hang_khach_hang(id):
    if current_user.role != EnumRole.khachHang:
        abort(403)

    don_hang = DonHang.query.get_or_404(id)
    if don_hang.idKH != current_user.id:
        abort(403)

    chi_tiet = ChiTietDonHang.query.filter_by(idDH=id).all()
    return render_template('restaurent/chi_tiet_don_hang.html', don_hang=don_hang, chi_tiet=chi_tiet)


@app.route('/nha-hang/don-hang/<int:id>/xac-nhan', methods=['POST'])
@login_required
def xac_nhan_don_hang(id):
    if current_user.role != EnumRole.nhaHang:
        return "Ban khong co quyen truy cap", 403

    don_hang = DonHang.query.get_or_404(id)
    if don_hang.idNhaHang != current_user.id:
        return "Khong co quyen xu ly don nay", 403

    if don_hang.trangThai != EnumStatus.cho:
        flash("Chi co the xac nhan don dang cho.", "warning")
    else:
        cap_nhat_trang_thai_don(don_hang, EnumStatus.daXacNhan)
        flash("Da xac nhan don hang.", "success")

    return redirect(url_for('quan_ly_don_hang'))


@app.route('/nha-hang/don-hang/<int:id>/hoan-tat', methods=['POST'])
@login_required
def hoan_tat_don_hang(id):
    if current_user.role != EnumRole.nhaHang:
        return "Ban khong co quyen truy cap", 403

    don_hang = DonHang.query.get_or_404(id)
    if don_hang.idNhaHang != current_user.id:
        return "Khong co quyen xu ly don nay", 403

    if don_hang.trangThai != EnumStatus.daXacNhan:
        flash("Chi co the hoan tat don da xac nhan.", "warning")
    else:
        cap_nhat_trang_thai_don(don_hang, EnumStatus.daGiao)
        flash("Da cap nhat don hang thanh da giao.", "success")

    return redirect(url_for('quan_ly_don_hang'))

@app.route("/mon-an/add", methods=['GET', 'POST'])
@login_required
def them_mon_an():
    if current_user.role != EnumRole.nhaHang:
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name')
        gia = request.form.get('gia')
        chi_tiet = request.form.get('chiTietMon')
        id_danh_muc = request.form.get('idDanhMuc')
        img = request.files.get('img')

        img_url = None
        if img:
            upload = cloudinary.uploader.upload(img)
            img_url = upload.get('secure_url')

        mon = MonAn(
            name=name,
            gia=float(gia),
            chiTietMon=chi_tiet,
            idDanhMuc=int(id_danh_muc),
            idNhaHang=current_user.id,
            img=img_url
        )
        db.session.add(mon)
        db.session.commit()

        return redirect(f"/nha-hang/{current_user.id}")

    danh_mucs = DanhMucMonAn.query.all()
    return render_template("restaurent/them_mon_an.html", danh_mucs=danh_mucs)


from flask import request
from datetime import datetime
from sqlalchemy import extract
import calendar

@app.route("/nha-hang/thong-ke-doanh-thu")
@login_required
def thong_ke_doanh_thu():
    if current_user.role != EnumRole.nhaHang:
        return "Không có quyền truy cập", 403


    thang = request.args.get('thang', type=int) or datetime.now().month
    nam = request.args.get('nam', type=int) or datetime.now().year


    don_hang = DonHang.query.filter(
        DonHang.idNhaHang == current_user.id,
        DonHang.trangThai == EnumStatus.daGiao,
        extract('month', DonHang.thoiGian) == thang,
        extract('year', DonHang.thoiGian) == nam
    ).all()


    tong_doanh_thu = sum(dh.tongGia for dh in don_hang)


    so_ngay = calendar.monthrange(nam, thang)[1]
    doanh_thu_ngay = [0] * so_ngay

    for dh in don_hang:
        ngay = dh.thoiGian.day
        doanh_thu_ngay[ngay - 1] += dh.tongGia

    return render_template("restaurent/thong_ke.html",
                           don_hang=don_hang,
                           tong_doanh_thu=tong_doanh_thu,
                           doanh_thu_ngay=doanh_thu_ngay,
                           thang=thang, nam=nam)
@app.route("/nha-hang/cap-nhat-thong-tin", methods=["GET", "POST"])
@login_required
def cap_nhat_nha_hang():
    if current_user.role != EnumRole.nhaHang:
        return "Không có quyền truy cập", 403

    nha_hang = NhaHang.query.get(current_user.id)

    if request.method == "POST":
        # Cập nhật thông tin cơ bản
        nha_hang.name = request.form["name"]
        nha_hang.email = request.form["email"]
        nha_hang.phone = request.form["phone"]
        nha_hang.adress = request.form["adress"]
        nha_hang.MST = request.form["MST"]
        nha_hang.gio_mo_cua = request.form["gio_mo_cua"]
        nha_hang.gio_dong_cua = request.form["gio_dong_cua"]

        # Cập nhật ảnh đại diện nếu có
        file = request.files.get('avt')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(current_app.root_path, 'static/uploads')
            os.makedirs(upload_folder, exist_ok=True)
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            nha_hang.avt = url_for('static', filename=f'uploads/{filename}')

        db.session.commit()
        flash("Cập nhật thông tin thành công!", "success")
        return redirect(url_for("chi_tiet_nha_hang", nha_hang_id=nha_hang.id))

    return render_template("restaurent/nha_hang_cap_nhat.html", nha_hang=nha_hang)

@app.context_processor
def inject_thong_bao():
    thong_bao = []
    chua_doc = 0
    so_mon_gio_hang = 0
    if current_user.is_authenticated:
        thong_bao = ThongBao.query.filter_by(user_id=current_user.id).order_by(ThongBao.thoi_gian.desc()).all()
        chua_doc = ThongBao.query.filter_by(user_id=current_user.id, da_doc=False).count()
        if current_user.role == EnumRole.khachHang:
            so_mon_gio_hang = sum(
                chi_tiet.soLuong
                for gio_hang in current_user.gio_hang
                for chi_tiet in gio_hang.chi_tiet_gio_hang
            )

    return dict(ds_thong_bao=thong_bao, so_thong_bao=chua_doc, so_mon_gio_hang=so_mon_gio_hang)

@app.route("/api/nha-hang/<int:nha_hang_id>/doi-trang-thai", methods=["POST"])
@login_required
def doi_trang_thai_hoat_dong(nha_hang_id):
    nha_hang = NhaHang.query.get_or_404(nha_hang_id)

    if current_user.id != nha_hang.id:
        return {"error": "Không có quyền thực hiện"}, 403

    nha_hang.dang_hoat_dong = not nha_hang.dang_hoat_dong
    db.session.commit()

    return {"dang_hoat_dong": nha_hang.dang_hoat_dong}

@app.route('/api/thong-bao/<int:id>/danh-dau-da-doc', methods=['POST'])
@login_required
def danh_dau_thong_bao(id):
    from app.models import ThongBao
    from app import db

    tb = ThongBao.query.get(id)
    if not tb or tb.user_id != current_user.id:
        return jsonify({'success': False}), 403

    tb.da_doc = True
    db.session.commit()

    return jsonify({'success': True})

@login.user_loader
def get_user_by_id(user_id):
    return dao.get_user_by_id(user_id)

# Chặn quyền truy cập vào admin
@app.before_request
def before_request():
    if '/admin' in request.path and not current_user.is_authenticated:
        return redirect('/login')

@app.route("/admin")
@login_required
def quan_tri():
    if current_user.role != EnumRole.admin:
        return "Bạn không có quyền truy cập", 403
    return redirect('/admin')

if __name__ == '__main__':
    socketio.run(app, debug=True)
