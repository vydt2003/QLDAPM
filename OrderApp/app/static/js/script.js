// --------------------- Cập nhật tình trạng món ăn ---------------------
async function capNhatTinhTrang(monId, tinhTrangMoi) {
    const button = document.getElementById('btnCapNhat' + monId);
    const statusText = document.getElementById('tinhtrang' + monId);

    button.disabled = true;
    button.innerText = 'Đang cập nhật...';

    try {
        const res = await fetch(`/api/cap-nhat-mon/${monId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ tinh_trang_moi: tinhTrangMoi })
        });

        if (res.ok) {
            const data = await res.json();

            // Cập nhật UI
            statusText.innerText = data.tinh_trang ? "Còn món" : "Hết món";
            statusText.className = data.tinh_trang ? "text-success" : "text-danger";

            button.innerText = data.tinh_trang ? "Đánh dấu hết món" : "Đánh dấu còn món";
            button.className = data.tinh_trang
                ? "btn btn-outline-danger btn-sm w-100"
                : "btn btn-outline-success btn-sm w-100";

            // Cập nhật onclick mới
            button.setAttribute("onclick", `capNhatTinhTrang(${monId}, ${!data.tinh_trang})`);
        } else {
            alert("Cập nhật thất bại!");
        }
    } catch (error) {
        alert("Lỗi kết nối server!");
        console.error(error);
    } finally {
        button.disabled = false;
    }
}

const socket = io();


if (currentUser.isAuthenticated === true) {
    socket.emit('join', { room: 'user_' + currentUser.id });
}

socket.on('thong_bao_moi', function (data) {
    const badge = document.getElementById('badge-so-thong-bao');
    const danhSach = document.getElementById('danhSachThongBao');

    if (badge && danhSach && data.noi_dung) {
        let so = parseInt(badge.innerText) || 0;
        so += 1;
        badge.innerText = so;

        if (badge.style.display === 'none') {
            badge.style.display = 'inline-block';
        }

        const newItem = document.createElement("li");
        newItem.classList.add("px-3", "py-2", "fw-bold");

        newItem.innerHTML = `
            <div class="small text-muted">${new Date().toLocaleTimeString()}</div>
            <div>${data.noi_dung}</div>
        `;

        const empty = danhSach.querySelector('.text-muted');
        if (empty) empty.remove();

        danhSach.appendChild(newItem);
    }

    // Hiện Swal
    Swal.fire({
        title: '🔔 Thông báo mới',
        text: data.noi_dung,
        icon: 'info',
        confirmButtonText: 'OK'
    });
});


async function doiTrangThaiHoatDong(nhaHangId) {
    const btn = document.getElementById("btnDoiTrangThai");
    const trangThaiSpan = document.getElementById("trangThaiHoatDong");

    btn.disabled = true;
    btn.innerText = "Đang xử lý...";

    try {
        const res = await fetch(`/api/nha-hang/${nhaHangId}/doi-trang-thai`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            }
        });

        if (res.ok) {
            const data = await res.json();
            const isOpen = data.dang_hoat_dong;

            trangThaiSpan.innerText = isOpen ? "Đang hoạt động" : "Đã đóng cửa";
            trangThaiSpan.className = isOpen ? "text-success" : "text-danger";

            btn.innerText = isOpen ? "Đóng quán" : "Mở quán";
        } else {
            alert("Cập nhật trạng thái thất bại!");
        }
    } catch (err) {
        alert("Lỗi kết nối đến server!");
        console.error(err);
    } finally {
        btn.disabled = false;
    }
}
document.addEventListener('DOMContentLoaded', () => {
    const thongBaoItems = document.querySelectorAll('.thong-bao-item');

    thongBaoItems.forEach(item => {
        item.addEventListener('click', async function () {
            const id = this.getAttribute('data-id');
            const url = this.getAttribute('data-url');

            if (!id || !url) return;

            try {
                const res = await fetch(`/api/thong-bao/${id}/danh-dau-da-doc`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                if (res.ok) {
                    // Giảm badge
                    const badge = document.getElementById('badge-so-thong-bao');
                    let so = parseInt(badge.innerText) || 0;
                    so = Math.max(so - 1, 0);
                    badge.innerText = so;
                    if (so === 0) badge.style.display = 'none';
                }

            } catch (err) {
                console.error('Lỗi đánh dấu đã đọc:', err);
            } finally {
                // Dù request thành công hay không vẫn chuyển trang
                window.location.href = url;
            }
        });
    });
});
