// 앱 초기화
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    setTodayDate();
    loadLastEntry();
});

// 앱 초기화
function initApp() {
    // PWA 설치 가능 이벤트 핸들러
    let installPrompt = null;

    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        installPrompt = e;
        console.log('설치 가능한 상태');
    });

    // Service Worker 등록
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('sw.js').catch(err => {
            console.log('Service Worker 등록 실패:', err);
        });
    }

    // 폼 제출 이벤트
    const form = document.getElementById('expenseForm');
    form.addEventListener('submit', handleFormSubmit);
}

// 오늘 날짜 설정
function setTodayDate() {
    const dateInput = document.getElementById('date');
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    dateInput.value = `${year}-${month}-${day}`;
}

// 폼 제출 처리
async function handleFormSubmit(e) {
    e.preventDefault();

    const button = e.target.querySelector('.btn-submit');
    button.disabled = true;

    // 폼 데이터 수집
    const formData = new FormData(e.target);
    const data = {
        date: formData.get('date'),
        amount: parseInt(formData.get('amount')),
        category: formData.get('category'),
        type: formData.get('type'),
        memo: formData.get('memo') || '',
        createdAt: new Date().toISOString()
    };

    // 유효성 검사
    if (!data.date || !data.amount || !data.category) {
        showMessage('❌ 필수 항목을 모두 입력하세요.', 'error');
        button.disabled = false;
        return;
    }

    showMessage('💾 저장 중...', 'loading');

    try {
        // API에 데이터 전송
        const response = await sendToNotion(data);

        if (response.ok || response.status === 201) {
            showMessage('✅ 가계부에 저장되었습니다!', 'success');

            // 폼 초기화
            e.target.reset();
            setTodayDate();

            // 최근 입력 저장
            saveLastEntry(data);
            updateLastEntry(data);

            // 3초 후 메시지 숨김
            setTimeout(() => {
                const msg = document.getElementById('statusMessage');
                msg.classList.remove('show');
            }, 3000);
        } else {
            const errorText = await response.text();
            console.error('API 응답 오류:', response.status, errorText);
            showMessage('❌ 저장 실패. 다시 시도하세요.', 'error');
        }
    } catch (error) {
        console.error('오류 발생:', error);
        showMessage('❌ 오류: ' + error.message, 'error');
    } finally {
        button.disabled = false;
    }
}

// Notion API에 데이터 전송
async function sendToNotion(data) {
    // 4단계에서 API 엔드포인트를 설정합니다
    // 현재는 로컬 개발용 엔드포인트입니다
    const apiUrl = '/api/expense';

    return fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    });
}

// 메시지 표시
function showMessage(message, type) {
    const messageEl = document.getElementById('statusMessage');
    messageEl.textContent = message;
    messageEl.className = `status-message show ${type}`;
}

// 최근 입력 저장 (로컬 스토리지)
function saveLastEntry(data) {
    try {
        localStorage.setItem('lastEntry', JSON.stringify(data));
    } catch (error) {
        console.log('localStorage 저장 실패:', error);
    }
}

// 최근 입력 표시
function updateLastEntry(data) {
    const dateStr = formatDate(data.date);
    const amountStr = formatAmount(data.amount);
    const categoryEmoji = getCategoryEmoji(data.category);
    const typeStr = data.type === '소비' ? '지출' : '수입';

    const lastEntryText = `${dateStr} • ${categoryEmoji} ${data.category} • ${typeStr} ${amountStr}`;
    document.getElementById('lastEntry').textContent = lastEntryText;
}

// 최근 입력 로드
function loadLastEntry() {
    try {
        const entry = localStorage.getItem('lastEntry');
        if (entry) {
            const data = JSON.parse(entry);
            updateLastEntry(data);
        }
    } catch (error) {
        console.log('localStorage 로드 실패:', error);
    }
}

// 유틸리티: 날짜 포맷
function formatDate(dateStr) {
    const date = new Date(dateStr + 'T00:00:00');
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${month}/${day}`;
}

// 유틸리티: 금액 포맷
function formatAmount(amount) {
    return `₩${amount.toLocaleString('ko-KR')}`;
}

// 유틸리티: 카테고리 이모지
function getCategoryEmoji(category) {
    const emojiMap = {
        '식비': '🍽️',
        '교통비': '🚗',
        '쇼핑': '🛍️',
        '의료': '🏥',
        '교육비': '📚',
        '취미': '🎬',
        '마트 장보기': '🛒',
        '기타': '📌'
    };
    return emojiMap[category] || '📌';
}