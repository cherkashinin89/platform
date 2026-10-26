"""
ВРЕМЕННЫЙ WOPI-каркас для проверки связи с Collabora (Этап 2).
Потом заменим на реальную логику (Этап 3).

Подключение в cloud/app.py:
    from wopi_test import wopi_test_bp
    app.register_blueprint(wopi_test_bp)
"""

from flask import Blueprint, jsonify, request

wopi_test_bp = Blueprint('wopi_test', __name__)


@wopi_test_bp.route('/wopi/files/<file_id>', methods=['GET'])
def wopi_check_file_info(file_id):
    """CheckFileInfo — минимальный набор полей для Collabora."""
    return jsonify({
        'BaseFileName': 'test.docx',
        'Size': 1024,
        'UserCanWrite': True,
        'UserFriendlyName': 'Test User',
        'UserId': 'test-user',
    })


@wopi_test_bp.route('/wopi/files/<file_id>/contents', methods=['GET'])
def wopi_get_file(file_id):
    """GetFile — отдаём пустой docx для проверки."""
    return (
        b'',
        200,
        {'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
    )


@wopi_test_bp.route('/wopi/files/<file_id>/contents', methods=['POST'])
def wopi_put_file(file_id):
    """PutFile — принимаем изменения (пока просто логируем)."""
    size = len(request.data)
    print(f'[WOPI] PutFile: file_id={file_id}, size={size}')
    return '', 200