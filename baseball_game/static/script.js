document.addEventListener('DOMContentLoaded', function() {
    const role = "{{ role }}";
    const turn = "{{ turn }}";
    const roomName = "{{ room_name }}"; // JavaScript 변수로 방 이름 설정

    if (turn === 'waiting') {
        document.getElementById('game-container').innerHTML = '<p>상대가 숫자를 결정하고 있습니다...</p>';
    } else {
        if (role === turn) {
            document.querySelector('form').style.display = 'block';
        } else {
            document.getElementById('game-container').innerHTML = '<p>상대의 입력을 기다리는 중...</p>';
        }
    }

    function checkTurn() {
        // 방 이름 변수를 사용하여 fetch 요청 보내기
        fetch(`/check_turn?room_name=${roomName}`)
            .then(response => response.json())
            .then(data => {
                if (data.turn !== turn) {
                    window.location.reload();
                }
            });
    }

    setInterval(checkTurn, 5000); // 5초마다 체크
});