# youtube_management.py 수정 버전
from datetime import datetime, date, timedelta
from flask import render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, and_, extract

# ❌ 기존 문제있는 코드:
# from app import app, db

# ✅ 수정된 코드: app 대신 current_app 사용, db는 models에서 import
from models import db, Editor, Work, Revenue, EditorRateHistory

def register_youtube_routes(app):
    """YouTube 관리 라우트들을 앱에 등록하는 함수"""
    
    @app.route('/youtube-management')
    @login_required
    def youtube_management():
        """YouTube 관리 시스템 메인 페이지"""
        if not current_user.is_approved():
            return redirect(url_for('pending'))
        
        return render_template('youtube_management.html')

    # 편집자 관리 API
    @app.route('/api/youtube/editors', methods=['GET'])
    @login_required
    def get_editors():
        """편집자 목록 조회"""
        editors = Editor.query.filter_by(user_id=current_user.id).all()
        return jsonify({
            "status": "success",
            "editors": [editor.to_dict() for editor in editors]
        })

    @app.route('/api/youtube/editors', methods=['POST'])
    @login_required
    def create_editor():
        """새 편집자 추가"""
        data = request.json
        
        try:
            editor = Editor(
                user_id=current_user.id,
                name=data['name'],
                contact=data.get('contact'),
                email=data.get('email'),
                basic_rate=data.get('basic_rate', 15000),
                japanese_rate=data.get('japanese_rate', 20000),
                notes=data.get('notes')
            )
            
            db.session.add(editor)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "편집자가 추가되었습니다.",
                "editor": editor.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "status": "error",
                "message": str(e)
            })

    @app.route('/api/youtube/editors/<int:editor_id>', methods=['PUT'])
    @login_required
    def update_editor(editor_id):
        """편집자 정보 수정 (단가 변경 이력 기록 포함)"""
        editor = Editor.query.filter_by(id=editor_id, user_id=current_user.id).first()
        
        if not editor:
            return jsonify({"status": "error", "message": "편집자를 찾을 수 없습니다."})
        
        data = request.json
        try:
            # 단가 변경 확인 및 이력 기록
            old_basic_rate = editor.basic_rate
            old_japanese_rate = editor.japanese_rate
            new_basic_rate = data.get('basic_rate', editor.basic_rate)
            new_japanese_rate = data.get('japanese_rate', editor.japanese_rate)
            
            rate_changed = (old_basic_rate != new_basic_rate or old_japanese_rate != new_japanese_rate)
            
            # 편집자 정보 업데이트
            editor.name = data.get('name', editor.name)
            editor.contact = data.get('contact', editor.contact)
            editor.email = data.get('email', editor.email)
            editor.basic_rate = new_basic_rate
            editor.japanese_rate = new_japanese_rate
            editor.status = data.get('status', editor.status)
            editor.notes = data.get('notes', editor.notes)
            editor.updated_at = datetime.utcnow()
            
            # 단가 변경 이력 기록
            if rate_changed:
                effective_date_str = data.get('effective_date')
                effective_date = datetime.strptime(effective_date_str, '%Y-%m-%d').date() if effective_date_str else date.today()
                
                rate_history = EditorRateHistory(
                    editor_id=editor.id,
                    user_id=current_user.id,
                    old_basic_rate=old_basic_rate,
                    new_basic_rate=new_basic_rate,
                    old_japanese_rate=old_japanese_rate,
                    new_japanese_rate=new_japanese_rate,
                    change_reason=data.get('change_reason', ''),
                    effective_date=effective_date
                )
                db.session.add(rate_history)
            
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "편집자 정보가 수정되었습니다." + (" (단가 변경 이력 기록됨)" if rate_changed else ""),
                "editor": editor.to_dict(),
                "rate_changed": rate_changed
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/editors/<int:editor_id>', methods=['DELETE'])
    @login_required
    def delete_editor(editor_id):
        """편집자 삭제"""
        editor = Editor.query.filter_by(id=editor_id, user_id=current_user.id).first()
        
        if not editor:
            return jsonify({"status": "error", "message": "편집자를 찾을 수 없습니다."})
        
        # 해당 편집자의 작업이 있는지 확인
        work_count = Work.query.filter_by(editor_id=editor_id).count()
        if work_count > 0:
            return jsonify({
                "status": "error", 
                "message": f"해당 편집자에게 {work_count}개의 작업이 있어 삭제할 수 없습니다."
            })
        
        try:
            db.session.delete(editor)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "편집자가 삭제되었습니다."
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/editors/<int:editor_id>/rate-history', methods=['GET'])
    @login_required
    def get_editor_rate_history(editor_id):
        """편집자 단가 변경 이력 조회"""
        editor = Editor.query.filter_by(id=editor_id, user_id=current_user.id).first()
        
        if not editor:
            return jsonify({"status": "error", "message": "편집자를 찾을 수 없습니다."})
        
        rate_history = EditorRateHistory.query.filter_by(editor_id=editor_id).order_by(EditorRateHistory.created_at.desc()).all()
        
        return jsonify({
            "status": "success",
            "editor_name": editor.name,
            "current_rates": {
                "basic_rate": editor.basic_rate,
                "japanese_rate": editor.japanese_rate
            },
            "history": [history.to_dict() for history in rate_history]
        })

    # 작업 관리 API
    @app.route('/api/youtube/works', methods=['GET'])
    @login_required
    def get_works():
        """작업 목록 조회"""
        # 날짜 필터링 옵션
        date_filter = request.args.get('date_filter', 'week')  # week, month, all
        
        query = Work.query.filter_by(user_id=current_user.id)
        
        if date_filter == 'week':
            # 이번 주 작업
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            query = query.filter(Work.work_date.between(week_start, week_end))
        elif date_filter == 'month':
            # 이번 달 작업
            today = date.today()
            month_start = today.replace(day=1)
            query = query.filter(Work.work_date >= month_start)
        
        works = query.order_by(Work.work_date.desc()).all()
        
        # 편집자별 지급 예정금액 계산
        editor_payments = {}
        for work in works:
            if work.status in ['completed', 'in_progress']:  # 완료 또는 진행중인 작업만
                editor_id = work.editor_id
                if editor_id not in editor_payments:
                    editor_payments[editor_id] = {
                        'editor_name': work.editor.name,
                        'total_amount': 0,
                        'work_count': 0
                    }
                editor_payments[editor_id]['total_amount'] += work.rate
                editor_payments[editor_id]['work_count'] += 1
        
        return jsonify({
            "status": "success",
            "works": [work.to_dict() for work in works],
            "editor_payments": editor_payments
        })

    @app.route('/api/youtube/works', methods=['POST'])
    @login_required
    def create_work():
        """새 작업 추가"""
        data = request.json
        
        try:
            # 편집자 확인
            editor = Editor.query.filter_by(
                id=data['editor_id'], 
                user_id=current_user.id
            ).first()
            
            if not editor:
                return jsonify({"status": "error", "message": "편집자를 찾을 수 없습니다."})
            
            # 작업 유형에 따른 단가 설정
            work_type = data['work_type']
            rate = editor.japanese_rate if work_type == 'japanese' else editor.basic_rate
            
            work = Work(
                user_id=current_user.id,
                editor_id=data['editor_id'],
                title=data['title'],
                work_type=work_type,
                work_date=datetime.strptime(data['work_date'], '%Y-%m-%d').date(),
                deadline=datetime.strptime(data['deadline'], '%Y-%m-%d').date() if data.get('deadline') else None,
                rate=rate,
                notes=data.get('notes')
            )
            
            db.session.add(work)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "작업이 추가되었습니다.",
                "work": work.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/works/<int:work_id>', methods=['PUT'])
    @login_required
    def update_work(work_id):
        """작업 정보 전체 수정"""
        work = Work.query.filter_by(id=work_id, user_id=current_user.id).first()
        
        if not work:
            return jsonify({"status": "error", "message": "작업을 찾을 수 없습니다."})
        
        data = request.json
        try:
            # 편집자 변경 시 확인
            if 'editor_id' in data and data['editor_id'] != work.editor_id:
                editor = Editor.query.filter_by(
                    id=data['editor_id'], 
                    user_id=current_user.id
                ).first()
                if not editor:
                    return jsonify({"status": "error", "message": "편집자를 찾을 수 없습니다."})
                work.editor_id = data['editor_id']
            
            # 작업 정보 업데이트
            if 'title' in data:
                work.title = data['title']
            if 'work_type' in data:
                work.work_type = data['work_type']
            if 'work_date' in data:
                work.work_date = datetime.strptime(data['work_date'], '%Y-%m-%d').date()
            if 'deadline' in data:
                work.deadline = datetime.strptime(data['deadline'], '%Y-%m-%d').date() if data['deadline'] else None
            if 'rate' in data:
                work.rate = data['rate']
            if 'status' in data:
                work.status = data['status']
            if 'notes' in data:
                work.notes = data['notes']
            
            work.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "작업 정보가 수정되었습니다.",
                "work": work.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/works/<int:work_id>/status', methods=['PUT'])
    @login_required
    def update_work_status(work_id):
        """작업 상태 변경 (기존 호환성 유지)"""
        work = Work.query.filter_by(id=work_id, user_id=current_user.id).first()
        
        if not work:
            return jsonify({"status": "error", "message": "작업을 찾을 수 없습니다."})
        
        data = request.json
        try:
            work.status = data['status']
            work.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "작업 상태가 변경되었습니다.",
                "work": work.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/works/<int:work_id>', methods=['DELETE'])
    @login_required
    def delete_work(work_id):
        """작업 삭제"""
        work = Work.query.filter_by(id=work_id, user_id=current_user.id).first()
        
        if not work:
            return jsonify({"status": "error", "message": "작업을 찾을 수 없습니다."})
        
        try:
            db.session.delete(work)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "작업이 삭제되었습니다."
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    # 수익 관리 API
    @app.route('/api/youtube/revenues', methods=['GET'])
    @login_required
    def get_revenues():
        """수익 목록 조회"""
        revenues = Revenue.query.filter_by(user_id=current_user.id).order_by(Revenue.year_month.desc()).all()
        
        return jsonify({
            "status": "success",
            "revenues": [revenue.to_dict() for revenue in revenues]
        })

    @app.route('/api/youtube/revenues', methods=['POST'])
    @login_required
    def create_revenue():
        """수익 데이터 추가"""
        data = request.json
        
        try:
            # 중복 체크
            existing = Revenue.query.filter_by(
                user_id=current_user.id,
                year_month=data['year_month']
            ).first()
            
            if existing:
                return jsonify({"status": "error", "message": "해당 월의 수익 데이터가 이미 존재합니다."})
            
            # 수익 데이터를 정수로 변환 (문자열로 전송된 경우 대비)
            youtube_revenue = int(data.get('youtube_revenue', 0))
            music_revenue = int(data.get('music_revenue', 0))
            other_revenue = int(data.get('other_revenue', 0))
            total_revenue = youtube_revenue + music_revenue + other_revenue
            
            revenue = Revenue(
                user_id=current_user.id,
                year_month=data['year_month'],
                youtube_revenue=youtube_revenue,
                music_revenue=music_revenue,
                other_revenue=other_revenue,
                total_revenue=total_revenue,
                notes=data.get('notes')
            )
            
            db.session.add(revenue)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "수익 데이터가 추가되었습니다.",
                "revenue": revenue.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/revenues/<int:revenue_id>', methods=['PUT'])
    @login_required
    def update_revenue(revenue_id):
        """수익 데이터 수정"""
        revenue = Revenue.query.filter_by(id=revenue_id, user_id=current_user.id).first()
        
        if not revenue:
            return jsonify({"status": "error", "message": "수익 데이터를 찾을 수 없습니다."})
        
        try:
            data = request.json
            
            # 다른 월에 동일한 year_month가 있는지 확인 (자기 자신 제외)
            if data.get('year_month') and data['year_month'] != revenue.year_month:
                existing = Revenue.query.filter_by(
                    user_id=current_user.id,
                    year_month=data['year_month']
                ).filter(Revenue.id != revenue_id).first()
                
                if existing:
                    return jsonify({"status": "error", "message": "해당 월의 수익 데이터가 이미 존재합니다."})
            
            # 수익 데이터 업데이트
            if 'year_month' in data:
                revenue.year_month = data['year_month']
            
            youtube_revenue = int(data.get('youtube_revenue', revenue.youtube_revenue or 0))
            music_revenue = int(data.get('music_revenue', revenue.music_revenue or 0))
            other_revenue = int(data.get('other_revenue', revenue.other_revenue or 0))
            
            revenue.youtube_revenue = youtube_revenue
            revenue.music_revenue = music_revenue
            revenue.other_revenue = other_revenue
            revenue.total_revenue = youtube_revenue + music_revenue + other_revenue
            
            if 'notes' in data:
                revenue.notes = data.get('notes')
            
            revenue.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "수익 데이터가 수정되었습니다.",
                "revenue": revenue.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/revenues/<int:revenue_id>', methods=['DELETE'])
    @login_required
    def delete_revenue(revenue_id):
        """수익 데이터 삭제"""
        revenue = Revenue.query.filter_by(id=revenue_id, user_id=current_user.id).first()
        
        if not revenue:
            return jsonify({"status": "error", "message": "수익 데이터를 찾을 수 없습니다."})
        
        try:
            db.session.delete(revenue)
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "수익 데이터가 삭제되었습니다."
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    # 대시보드 API
    @app.route('/api/youtube/dashboard', methods=['GET'])
    @login_required
    def get_dashboard_stats():
        """대시보드 통계 조회"""
        try:
            # 편집자 수
            total_editors = Editor.query.filter_by(user_id=current_user.id, status='active').count()
            
            # 이번 주 작업량 및 지급액
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            week_works = Work.query.filter(
                Work.user_id == current_user.id,
                Work.work_date.between(week_start, week_end)
            ).all()
            
            week_work_count = len(week_works)
            week_payment = sum(work.rate for work in week_works)
            
            # 이번 달 수익
            current_month = today.strftime('%Y-%m')
            month_revenue_data = Revenue.query.filter_by(
                user_id=current_user.id,
                year_month=current_month
            ).first()
            
            month_revenue = month_revenue_data.total_revenue if month_revenue_data else 0
            
            # 편집자별 성과 (이번 달)
            editor_stats = db.session.query(
                Editor.name,
                func.count(Work.id).label('work_count')
            ).join(Work).filter(
                Work.user_id == current_user.id,
                extract('year', Work.work_date) == today.year,
                extract('month', Work.work_date) == today.month
            ).group_by(Editor.id, Editor.name).order_by(func.count(Work.id).desc()).all()
            
            # 요일별 작업 현황
            daily_stats = {}
            weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일']
            
            for i, day_name in enumerate(weekdays):
                day_date = week_start + timedelta(days=i)
                day_works = [w for w in week_works if w.work_date == day_date]
                daily_stats[day_name] = {
                    'count': len(day_works),
                    'status': 'completed' if len(day_works) > 0 else 'pending'
                }
            
            return jsonify({
                "status": "success",
                "stats": {
                    "total_editors": total_editors,
                    "week_work_count": week_work_count,
                    "week_payment": week_payment,
                    "month_revenue": month_revenue,
                    "editor_rankings": [
                        {"name": stat.name, "work_count": stat.work_count}
                        for stat in editor_stats
                    ],
                    "daily_stats": daily_stats
                }
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})

    # 데이터 내보내기/가져오기 API
    @app.route('/api/youtube/export', methods=['GET'])
    @login_required
    def export_youtube_data():
        """YouTube 관리 데이터 내보내기"""
        try:
            editors = Editor.query.filter_by(user_id=current_user.id).all()
            works = Work.query.filter_by(user_id=current_user.id).all()
            revenues = Revenue.query.filter_by(user_id=current_user.id).all()
            
            export_data = {
                "export_date": datetime.utcnow().isoformat(),
                "user_email": current_user.email,
                "version": "1.0",
                "editors": [editor.to_dict() for editor in editors],
                "works": [work.to_dict() for work in works],
                "revenues": [revenue.to_dict() for revenue in revenues]
            }
            
            return jsonify({
                "status": "success",
                "data": export_data
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/import', methods=['POST'])
    @login_required
    def import_youtube_data():
        """YouTube 관리 데이터 가져오기"""
        data = request.json
        
        try:
            # 기존 데이터 백업 (옵션)
            if data.get('backup_existing', True):
                # 백업 로직 구현 가능
                pass
            
            # 데이터 가져오기
            imported_count = {
                'editors': 0,
                'works': 0,
                'revenues': 0
            }
            
            # 편집자 데이터 가져오기
            for editor_data in data.get('editors', []):
                if not Editor.query.filter_by(user_id=current_user.id, name=editor_data['name']).first():
                    editor = Editor(
                        user_id=current_user.id,
                        name=editor_data['name'],
                        contact=editor_data.get('contact'),
                        email=editor_data.get('email'),
                        basic_rate=editor_data.get('basic_rate', 15000),
                        japanese_rate=editor_data.get('japanese_rate', 20000),
                        notes=editor_data.get('notes')
                    )
                    db.session.add(editor)
                    imported_count['editors'] += 1
            
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": "데이터 가져오기가 완료되었습니다.",
                "imported_count": imported_count
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})