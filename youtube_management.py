import logging
# youtube_management.py 수정 버전
from datetime import datetime, date, timedelta
from flask import render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, and_, extract, text

# ❌ 기존 문제있는 코드:
# from app import app, db

# ✅ 수정된 코드: app 대신 current_app 사용, db는 models에서 import
from models import db, Editor, Work, Revenue, EditorRateHistory
logger = logging.getLogger(__name__)

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
        try:
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
            works_data = []
            
            for work in works:
                try:
                    # work.to_dict() 호출하면서 에러 처리
                    work_dict = work.to_dict()
                    works_data.append(work_dict)
                    
                    # 편집자별 지급 예정금액 계산 (편집자가 존재하는 경우만)
                    if work.status in ['completed', 'in_progress'] and work.editor:  # 편집자가 존재하는지 확인
                        editor_id = work.editor_id
                        if editor_id not in editor_payments:
                            editor_payments[editor_id] = {
                                'editor_name': work.editor.name,
                                'total_amount': 0,
                                'work_count': 0
                            }
                        editor_payments[editor_id]['total_amount'] += work.rate
                        editor_payments[editor_id]['work_count'] += 1
                        
                except Exception as work_error:
                    current_app.logger.error(f"작업 데이터 처리 중 에러 (Work ID: {work.id}): {str(work_error)}")
                    # 기본 데이터라도 반환
                    works_data.append({
                        'id': work.id,
                        'title': work.title or '제목 없음',
                        'work_type': work.work_type or 'basic',
                        'work_date': work.work_date.isoformat() if work.work_date else None,
                        'deadline': work.deadline.isoformat() if work.deadline else None,
                        'rate': work.rate or 0,
                        'status': work.status or 'pending',
                        'notes': work.notes or '',
                        'editor_name': work.editor.name if work.editor else '편집자 정보 없음',
                        'created_at': work.created_at.isoformat() if work.created_at else None,
                        'updated_at': work.updated_at.isoformat() if work.updated_at else None
                    })
            
            return jsonify({
                "status": "success",
                "works": works_data,
                "editor_payments": editor_payments
            })
            
        except Exception as e:
            current_app.logger.error(f"작업 목록 조회 중 에러: {str(e)}")
            return jsonify({
                "status": "error", 
                "message": f"작업 목록을 불러오는 중 오류가 발생했습니다: {str(e)}"
            }), 500

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
        try:
            # 데이터베이스 연결 확인
            db.session.execute(text("SELECT 1"))
            
            revenues = Revenue.query.filter_by(user_id=current_user.id).order_by(Revenue.year_month.desc()).all()
            print(f"수익 데이터 조회: 사용자 {current_user.id}, {len(revenues)}개 항목 발견")
            
            revenue_list = []
            for revenue in revenues:
                try:
                    revenue_dict = revenue.to_dict()
                    revenue_list.append(revenue_dict)
                except Exception as e:
                    # 개별 수익 데이터 변환 실패 시 스킵하고 로그 남김
                    print(f"Revenue to_dict 오류: {str(e)}, Revenue ID: {getattr(revenue, 'id', 'Unknown')}")
                    continue
            
            print(f"수익 데이터 처리 완료: {len(revenue_list)}개 항목")
            return jsonify({
                "status": "success",
                "revenues": revenue_list
            })
        except Exception as e:
            print(f"수익 데이터 조회 오류: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "status": "error",
                "message": f"수익 데이터를 불러오는 중 오류가 발생했습니다: {str(e)}"
            }), 500

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
            
            # 수익 데이터를 정수로 변환 (콤마 제거 후)
            def parse_revenue(value):
                """수익 값에서 콤마를 제거하고 정수로 변환"""
                if isinstance(value, str):
                    value = value.replace(',', '').replace('원', '').strip()
                try:
                    return int(float(value)) if value else 0
                except (ValueError, TypeError):
                    return 0
            
            youtube_revenue = parse_revenue(data.get('youtube_revenue', 0))
            music_revenue = parse_revenue(data.get('music_revenue', 0))
            other_revenue = parse_revenue(data.get('other_revenue', 0))
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
            
            # 수익 데이터를 정수로 변환 (콤마 제거 후)
            def parse_revenue(value, fallback=0):
                """수익 값에서 콤마를 제거하고 정수로 변환"""
                if isinstance(value, str):
                    value = value.replace(',', '').replace('원', '').strip()
                try:
                    return int(float(value)) if value else fallback
                except (ValueError, TypeError):
                    return fallback
            
            youtube_revenue = parse_revenue(data.get('youtube_revenue'), revenue.youtube_revenue or 0)
            music_revenue = parse_revenue(data.get('music_revenue'), revenue.music_revenue or 0)
            other_revenue = parse_revenue(data.get('other_revenue'), revenue.other_revenue or 0)
            
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

    # 정산 관리 API
    @app.route('/api/youtube/settlements/weekly', methods=['GET'])
    @login_required
    def get_weekly_settlements():
        """주간 정산 조회 - 특정 주의 완료된 작업 조회"""
        try:
            # 쿼리 파라미터에서 주간 정보 가져오기
            year = request.args.get('year', type=int)
            week = request.args.get('week', type=int)
            
            if not year or not week:
                # 기본값: 현재 주
                today = date.today()
                year = today.year
                week = today.isocalendar()[1]
            
            # ISO 8601 기준으로 해당 주의 시작일과 종료일 계산 (월요일 시작)
            # 해당 연도 1월 4일이 첫 번째 주에 속함 (ISO 8601 표준)
            jan4 = date(year, 1, 4)
            week1_monday = jan4 - timedelta(days=jan4.weekday())  # 첫 번째 주의 월요일
            week_start = week1_monday + timedelta(weeks=week-1)  # 지정한 주의 월요일
            week_end = week_start + timedelta(days=6)  # 일요일
            
            # 완료된 작업 조회 (디버깅 정보 추가)
            completed_works = Work.query.filter(
                Work.user_id == current_user.id,
                Work.status == 'completed',
                Work.work_date.between(week_start, week_end)
            ).order_by(Work.work_date, Work.created_at).all()
            
            # 디버깅: 모든 완료된 작업 조회 (비교용)
            all_completed_works = Work.query.filter(
                Work.user_id == current_user.id,
                Work.status == 'completed'
            ).order_by(Work.work_date.desc()).limit(20).all()
            
            print(f"Settlement query - Year: {year}, Week: {week}")
            print(f"Date range: {week_start} to {week_end}")
            print(f"Found {len(completed_works)} completed works in date range")
            print(f"Total completed works (recent 20): {len(all_completed_works)}")
            
            print("Recent completed works:")
            for work in all_completed_works:
                in_range = week_start <= work.work_date <= week_end
                print(f"  - Work ID: {work.id}, Date: {work.work_date}, Status: {work.status}, Settlement: {work.settlement_status}, In Range: {in_range}")
            
            print("Works in selected date range:")
            for work in completed_works:
                print(f"  - Work ID: {work.id}, Date: {work.work_date}, Status: {work.status}, Settlement: {work.settlement_status}")
            
            # 편집자별 집계
            editor_summary = {}
            total_amount = 0
            
            for work in completed_works:
                editor_id = work.editor_id
                editor_name = work.editor.name if work.editor else "알 수 없는 편집자"
                
                if editor_id not in editor_summary:
                    editor_summary[editor_id] = {
                        'editor_name': editor_name,
                        'basic_count': 0,
                        'japanese_count': 0,
                        'basic_amount': 0,
                        'japanese_amount': 0,
                        'total_amount': 0,
                        'works': []
                    }
                
                work_dict = work.to_dict()
                editor_summary[editor_id]['works'].append(work_dict)
                
                if work.work_type == 'basic':
                    editor_summary[editor_id]['basic_count'] += 1
                    editor_summary[editor_id]['basic_amount'] += work.rate
                elif work.work_type == 'japanese':
                    editor_summary[editor_id]['japanese_count'] += 1
                    editor_summary[editor_id]['japanese_amount'] += work.rate
                
                editor_summary[editor_id]['total_amount'] += work.rate
                total_amount += work.rate
            
            return jsonify({
                "status": "success",
                "works": [work.to_dict() for work in completed_works],
                "data": {
                    "year": year,
                    "week": week,
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "date_range": f"{week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')}",
                    "total_works": len(completed_works),
                    "total_amount": total_amount,
                    "editor_summary": list(editor_summary.values())
                }
            })
        except Exception as e:
            print(f"Settlement API error: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"정산 데이터 조회 중 오류가 발생했습니다: {str(e)}"})

    @app.route('/api/youtube/settlements/editor-summary', methods=['GET'])
    @login_required
    def get_editor_settlement_summary():
        """편집자별 집계 - 기본/일본어 작업 구분 계산"""
        try:
            # 쿼리 파라미터
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            editor_id = request.args.get('editor_id', type=int)
            settlement_status = request.args.get('settlement_status', 'all')

            logger.info(f"[editor-summary] 파라미터 - start: {start_date}, end: {end_date}, editor_id: {editor_id}, status: {settlement_status}")

            # 기본 쿼리
            query = Work.query.filter(
                Work.user_id == current_user.id,
                Work.status == 'completed'
            )

            # 날짜 필터
            if start_date:
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    query = query.filter(Work.work_date >= start_date_obj)
                    logger.info(f"[editor-summary] start_date 필터: {start_date_obj}")
                except ValueError:
                    logger.warning(f"[editor-summary] 유효하지 않은 start_date: {start_date}")

            if end_date:
                try:
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    query = query.filter(Work.work_date <= end_date_obj)
                    logger.info(f"[editor-summary] end_date 필터: {end_date_obj}")
                except ValueError:
                    logger.warning(f"[editor-summary] 유효하지 않은 end_date: {end_date}")

            if editor_id:
                query = query.filter(Work.editor_id == editor_id)
                logger.info(f"[editor-summary] editor_id 필터: {editor_id}")

            if settlement_status != 'all':
                query = query.filter(Work.settlement_status == settlement_status)
                logger.info(f"[editor-summary] settlement_status 필터: {settlement_status}")

            works = query.order_by(Work.work_date.desc()).all()
            logger.info(f"[editor-summary] 조회된 작업 수: {len(works)}")

            # 집계
            editor_stats = {}
            grand_total = {
                'basic_count': 0,
                'japanese_count': 0,
                'basic_amount': 0,
                'japanese_amount': 0,
                'total_count': 0,
                'total_amount': 0,
                'pending_amount': 0,
                'settled_amount': 0
            }

            for work in works:
                editor_key = work.editor_id
                try:
                    editor_name = work.editor.name if work.editor else "알 수 없음"
                except Exception as e:
                    logger.warning(f"[editor-summary] editor.name 접근 실패 (editor_id: {editor_key}): {e}")
                    editor_name = "알 수 없음"

                if editor_key not in editor_stats:
                    editor_stats[editor_key] = {
                        'editor_id': editor_key,
                        'editor_name': editor_name,
                        'basic_count': 0,
                        'japanese_count': 0,
                        'basic_amount': 0,
                        'japanese_amount': 0,
                        'total_count': 0,
                        'total_amount': 0,
                        'pending_count': 0,
                        'settled_count': 0,
                        'pending_amount': 0,
                        'settled_amount': 0
                    }

                stats = editor_stats[editor_key]

                # 작업 유형별
                if work.work_type == 'basic':
                    stats['basic_count'] += 1
                    stats['basic_amount'] += work.rate
                    grand_total['basic_count'] += 1
                    grand_total['basic_amount'] += work.rate
                elif work.work_type == 'japanese':
                    stats['japanese_count'] += 1
                    stats['japanese_amount'] += work.rate
                    grand_total['japanese_count'] += 1
                    grand_total['japanese_amount'] += work.rate

                # 정산 상태별
                if work.settlement_status == 'pending':
                    stats['pending_count'] += 1
                    stats['pending_amount'] += work.rate
                    grand_total['pending_amount'] += work.rate
                elif work.settlement_status == 'settled':
                    stats['settled_count'] += 1
                    stats['settled_amount'] += work.rate
                    grand_total['settled_amount'] += work.rate

                # 전체 합계
                stats['total_count'] += 1
                stats['total_amount'] += work.rate
                grand_total['total_count'] += 1
                grand_total['total_amount'] += work.rate

            result = {
                "status": "success",
                "data": {
                    "filters": {
                        "start_date": start_date,
                        "end_date": end_date,
                        "editor_id": editor_id,
                        "settlement_status": settlement_status
                    },
                    "editor_stats": list(editor_stats.values()),
                    "grand_total": grand_total,
                    "total_works": len(works)
                }
            }

            logger.info("[editor-summary] 최종 응답:\n%s", safe_json(result))
            return jsonify(result)

        except Exception as e:
            logger.exception("[editor-summary] 예외 발생:")
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/settlements/complete', methods=['POST'])
    @login_required
    def complete_settlements():
        """정산 완료 처리 - 정산 상태 관리"""
        try:
            data = request.json
            work_ids = data.get('work_ids', [])
            settlement_date = data.get('settlement_date')
            notes = data.get('notes', '')
            
            if not work_ids:
                return jsonify({"status": "error", "message": "정산할 작업을 선택해주세요."})
            
            # 정산 날짜 파싱
            if settlement_date:
                try:
                    settlement_date_obj = datetime.strptime(settlement_date, '%Y-%m-%d').date()
                except ValueError:
                    return jsonify({"status": "error", "message": "잘못된 날짜 형식입니다."})
            else:
                settlement_date_obj = date.today()
            
            # 해당 작업들 조회 및 권한 확인
            works = Work.query.filter(
                Work.id.in_(work_ids),
                Work.user_id == current_user.id,
                Work.status == 'completed',
                Work.settlement_status == 'pending'
            ).all()
            
            if len(works) != len(work_ids):
                return jsonify({
                    "status": "error", 
                    "message": "일부 작업을 찾을 수 없거나 이미 정산된 작업입니다."
                })
            
            # 정산 처리
            updated_count = 0
            total_amount = 0
            
            for work in works:
                work.settlement_status = 'settled'
                work.settlement_date = settlement_date_obj
                work.settlement_amount = work.rate  # 정산 금액은 기본적으로 작업 단가와 동일
                if notes:
                    work.notes = (work.notes or '') + f'\n[정산 완료: {settlement_date_obj}] {notes}'
                work.updated_at = datetime.utcnow()
                
                updated_count += 1
                total_amount += work.rate
            
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": f"{updated_count}개 작업의 정산이 완료되었습니다.",
                "data": {
                    "updated_count": updated_count,
                    "total_amount": total_amount,
                    "settlement_date": settlement_date_obj.isoformat()
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})

    @app.route('/api/youtube/settlements/revert', methods=['POST'])
    @login_required
    def revert_settlements():
        """정산 되돌리기"""
        try:
            data = request.json
            work_ids = data.get('work_ids', [])
            
            if not work_ids:
                return jsonify({"status": "error", "message": "되돌릴 작업을 선택해주세요."})
            
            # 해당 작업들 조회 및 권한 확인
            works = Work.query.filter(
                Work.id.in_(work_ids),
                Work.user_id == current_user.id,
                Work.settlement_status == 'settled'
            ).all()
            
            if len(works) != len(work_ids):
                return jsonify({
                    "status": "error", 
                    "message": "일부 작업을 찾을 수 없거나 이미 미정산 상태입니다."
                })
            
            # 정산 되돌리기
            updated_count = 0
            
            for work in works:
                work.settlement_status = 'pending'
                work.settlement_date = None
                work.settlement_amount = None
                work.updated_at = datetime.utcnow()
                
                updated_count += 1
            
            db.session.commit()
            
            return jsonify({
                "status": "success",
                "message": f"{updated_count}개 작업의 정산이 되돌려졌습니다.",
                "data": {
                    "updated_count": updated_count
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)})