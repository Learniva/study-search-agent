"""
Database operations for grading system.

High-level functions for common database operations.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func

from database.models import (
    User,
    GradingSession,
    RubricTemplate,
    ProfessorConfiguration,
    AuditLog,
    GradingStatistics
)


def get_or_create_user(
    db: Session,
    user_id: str,
    role: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    lms_type: Optional[str] = None,
    course_id: Optional[str] = None
) -> User:
    """
    Get existing user or create new one.
    
    Args:
        db: Database session
        user_id: External user ID (from LMS or auth system)
        role: User role (student, teacher, admin)
        email: User email
        name: User name
        lms_type: LMS type (canvas, google_classroom)
        course_id: Course ID
        
    Returns:
        User object
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    
    if user:
        # Update last active time
        user.last_active = datetime.utcnow()
        db.commit()
        return user
    
    # Create new user
    user = User(
        user_id=user_id,
        role=role,
        email=email,
        name=name,
        lms_type=lms_type,
        course_id=course_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create default configuration for professors
    if role in ["teacher", "instructor", "professor", "admin"]:
        config = ProfessorConfiguration(professor_id=user.id)
        db.add(config)
        db.commit()
    
    return user


def save_grading_session(
    db: Session,
    professor_id: str,
    grading_type: str,
    submission: Dict[str, Any],
    ai_feedback: Dict[str, Any],
    student_id: Optional[str] = None,
    student_name: Optional[str] = None,
    course_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
    assignment_name: Optional[str] = None,
    score: Optional[float] = None,
    max_score: Optional[float] = None,
    rubric_id: Optional[str] = None,
    agent_used: Optional[str] = None,
    processing_time: Optional[float] = None
) -> GradingSession:
    """
    Save a grading session to the database.
    
    Args:
        db: Database session
        professor_id: Professor's user ID
        grading_type: Type of grading (essay, code, mcq, etc.)
        submission: Student submission data
        ai_feedback: AI-generated feedback
        student_id: Student ID
        student_name: Student name
        course_id: Course ID
        assignment_id: Assignment ID
        assignment_name: Assignment name
        score: Score received
        max_score: Maximum possible score
        rubric_id: Rubric template ID (if used)
        agent_used: Which grading tool was used
        processing_time: Time taken to grade (seconds)
        
    Returns:
        GradingSession object
    """
    # Get professor's database ID
    professor = db.query(User).filter(User.user_id == professor_id).first()
    if not professor:
        raise ValueError(f"Professor with user_id={professor_id} not found")
    
    # Calculate percentage
    percentage = None
    if score is not None and max_score is not None and max_score > 0:
        percentage = (score / max_score) * 100
    
    # Determine grade letter
    grade_letter = None
    if percentage is not None:
        if percentage >= 90:
            grade_letter = "A"
        elif percentage >= 80:
            grade_letter = "B"
        elif percentage >= 70:
            grade_letter = "C"
        elif percentage >= 60:
            grade_letter = "D"
        else:
            grade_letter = "F"
    
    # Extract AI confidence if available
    ai_confidence = ai_feedback.get("confidence", 0.0) if isinstance(ai_feedback, dict) else None
    
    # Create grading session
    session = GradingSession(
        professor_id=professor.id,
        student_id=student_id,
        student_name=student_name,
        course_id=course_id,
        assignment_id=assignment_id,
        assignment_name=assignment_name,
        grading_type=grading_type,
        submission=submission,
        score=score,
        max_score=max_score,
        percentage=percentage,
        grade_letter=grade_letter,
        ai_feedback=ai_feedback,
        rubric_id=rubric_id,
        agent_used=agent_used,
        ai_confidence=ai_confidence,
        processing_time_seconds=processing_time
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return session


def get_grading_history(
    db: Session,
    professor_id: str,
    limit: int = 50,
    offset: int = 0,
    course_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
    grading_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[GradingSession]:
    """
    Get grading history for a professor.
    
    Args:
        db: Database session
        professor_id: Professor's user ID
        limit: Maximum number of results
        offset: Offset for pagination
        course_id: Filter by course (optional)
        assignment_id: Filter by assignment (optional)
        grading_type: Filter by grading type (optional)
        start_date: Filter by start date (optional)
        end_date: Filter by end date (optional)
        
    Returns:
        List of GradingSession objects
    """
    # Get professor's database ID
    professor = db.query(User).filter(User.user_id == professor_id).first()
    if not professor:
        return []
    
    # Build query
    query = db.query(GradingSession).filter(GradingSession.professor_id == professor.id)
    
    # Apply filters
    if course_id:
        query = query.filter(GradingSession.course_id == course_id)
    if assignment_id:
        query = query.filter(GradingSession.assignment_id == assignment_id)
    if grading_type:
        query = query.filter(GradingSession.grading_type == grading_type)
    if start_date:
        query = query.filter(GradingSession.created_at >= start_date)
    if end_date:
        query = query.filter(GradingSession.created_at <= end_date)
    
    # Order by most recent first
    query = query.order_by(desc(GradingSession.created_at))
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    return query.all()


def save_rubric_template(
    db: Session,
    professor_id: str,
    name: str,
    rubric_type: str,
    criteria: Dict[str, Any],
    max_score: float,
    description: Optional[str] = None,
    is_public: bool = False
) -> RubricTemplate:
    """
    Save a rubric template.
    
    Args:
        db: Database session
        professor_id: Professor's user ID
        name: Rubric name
        rubric_type: Type (essay, code, etc.)
        criteria: Rubric criteria structure
        max_score: Maximum score
        description: Description (optional)
        is_public: Whether other professors can use (optional)
        
    Returns:
        RubricTemplate object
    """
    # Get professor's database ID
    professor = db.query(User).filter(User.user_id == professor_id).first()
    if not professor:
        raise ValueError(f"Professor with user_id={professor_id} not found")
    
    rubric = RubricTemplate(
        professor_id=professor.id,
        name=name,
        rubric_type=rubric_type,
        criteria=criteria,
        max_score=max_score,
        description=description,
        is_public=is_public
    )
    
    db.add(rubric)
    db.commit()
    db.refresh(rubric)
    
    return rubric


def get_rubric_templates(
    db: Session,
    professor_id: str,
    rubric_type: Optional[str] = None,
    include_public: bool = True
) -> List[RubricTemplate]:
    """
    Get rubric templates for a professor.
    
    Args:
        db: Database session
        professor_id: Professor's user ID
        rubric_type: Filter by type (optional)
        include_public: Include public rubrics (optional)
        
    Returns:
        List of RubricTemplate objects
    """
    # Get professor's database ID
    professor = db.query(User).filter(User.user_id == professor_id).first()
    if not professor:
        return []
    
    # Query professor's rubrics
    query = db.query(RubricTemplate).filter(
        RubricTemplate.professor_id == professor.id
    )
    
    # Add public rubrics if requested
    if include_public:
        query = query.union(
            db.query(RubricTemplate).filter(RubricTemplate.is_public == True)
        )
    
    # Filter by type if specified
    if rubric_type:
        query = query.filter(RubricTemplate.rubric_type == rubric_type)
    
    return query.all()


def log_audit(
    db: Session,
    user_id: str,
    action_type: str,
    user_role: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action_details: Optional[Dict[str, Any]] = None,
    course_id: Optional[str] = None,
    student_id: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """
    Log an audit entry.
    
    Args:
        db: Database session
        user_id: User ID
        action_type: Type of action
        user_role: User role
        resource_type: Type of resource affected
        resource_id: ID of resource affected
        action_details: Detailed action information
        course_id: Course ID (optional)
        student_id: Student ID (optional)
        success: Whether action succeeded
        error_message: Error message if failed
        ip_address: User's IP address
        
    Returns:
        AuditLog object
    """
    log = AuditLog(
        user_id=user_id,
        user_role=user_role,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        action_details=action_details,
        course_id=course_id,
        student_id=student_id,
        success=success,
        error_message=error_message,
        ip_address=ip_address
    )
    
    db.add(log)
    db.commit()
    db.refresh(log)
    
    return log


def update_grading_statistics(
    db: Session,
    professor_id: str,
    course_id: Optional[str] = None,
    period: str = "daily"
):
    """
    Update aggregated statistics for a professor.
    
    This should be called periodically (e.g., nightly) to update stats.
    
    Args:
        db: Database session
        professor_id: Professor's user ID
        course_id: Course ID (optional)
        period: Period for aggregation (daily, weekly, monthly)
    """
    # Get professor's database ID
    professor = db.query(User).filter(User.user_id == professor_id).first()
    if not professor:
        return
    
    # Determine date range
    now = datetime.utcnow()
    if period == "daily":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # monthly
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Query grading sessions for this period
    query = db.query(GradingSession).filter(
        and_(
            GradingSession.professor_id == professor.id,
            GradingSession.created_at >= start_date
        )
    )
    
    if course_id:
        query = query.filter(GradingSession.course_id == course_id)
    
    sessions = query.all()
    
    if not sessions:
        return
    
    # Calculate statistics
    total_gradings = len(sessions)
    avg_score = sum(s.score for s in sessions if s.score) / total_gradings if total_gradings > 0 else 0
    avg_processing_time = sum(s.processing_time_seconds for s in sessions if s.processing_time_seconds) / total_gradings if total_gradings > 0 else 0
    total_students = len(set(s.student_id for s in sessions if s.student_id))
    
    # Count by type
    essay_count = sum(1 for s in sessions if s.grading_type == "essay")
    code_count = sum(1 for s in sessions if s.grading_type == "code")
    mcq_count = sum(1 for s in sessions if s.grading_type == "mcq")
    
    # AI metrics
    ai_confidences = [s.ai_confidence for s in sessions if s.ai_confidence]
    avg_ai_confidence = sum(ai_confidences) / len(ai_confidences) if ai_confidences else 0
    manual_adjustments = sum(1 for s in sessions if s.professor_adjusted_score is not None)
    
    # Check if stats already exist
    existing_stats = db.query(GradingStatistics).filter(
        and_(
            GradingStatistics.professor_id == professor.id,
            GradingStatistics.course_id == course_id,
            GradingStatistics.period == period,
            GradingStatistics.date == start_date
        )
    ).first()
    
    if existing_stats:
        # Update existing
        existing_stats.total_gradings = total_gradings
        existing_stats.avg_score = avg_score
        existing_stats.avg_processing_time = avg_processing_time
        existing_stats.total_students = total_students
        existing_stats.essay_count = essay_count
        existing_stats.code_count = code_count
        existing_stats.mcq_count = mcq_count
        existing_stats.avg_ai_confidence = avg_ai_confidence
        existing_stats.manual_adjustments = manual_adjustments
        existing_stats.updated_at = datetime.utcnow()
    else:
        # Create new
        stats = GradingStatistics(
            professor_id=professor.id,
            course_id=course_id,
            period=period,
            date=start_date,
            total_gradings=total_gradings,
            avg_score=avg_score,
            avg_processing_time=avg_processing_time,
            total_students=total_students,
            essay_count=essay_count,
            code_count=code_count,
            mcq_count=mcq_count,
            avg_ai_confidence=avg_ai_confidence,
            manual_adjustments=manual_adjustments
        )
        db.add(stats)
    
    db.commit()


def get_professor_config(db: Session, professor_id: str) -> Optional[ProfessorConfiguration]:
    """
    Get professor configuration.
    
    Args:
        db: Database session
        professor_id: Professor's user ID
        
    Returns:
        ProfessorConfiguration object or None
    """
    professor = db.query(User).filter(User.user_id == professor_id).first()
    if not professor:
        return None
    
    return db.query(ProfessorConfiguration).filter(
        ProfessorConfiguration.professor_id == professor.id
    ).first()


def update_professor_config(
    db: Session,
    professor_id: str,
    **kwargs
) -> ProfessorConfiguration:
    """
    Update professor configuration.
    
    Args:
        db: Database session
        professor_id: Professor's user ID
        **kwargs: Configuration fields to update
        
    Returns:
        Updated ProfessorConfiguration object
    """
    professor = db.query(User).filter(User.user_id == professor_id).first()
    if not professor:
        raise ValueError(f"Professor with user_id={professor_id} not found")
    
    config = get_professor_config(db, professor_id)
    
    if not config:
        config = ProfessorConfiguration(professor_id=professor.id)
        db.add(config)
    
    # Update fields
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    
    return config


# Aliases for backward compatibility
def update_grading_session(db: Session, session_id: str, **kwargs):
    """Update a grading session with new data."""
    session = db.query(GradingSession).filter(GradingSession.id == session_id).first()
    if session:
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
    return session


def update_rubric_template(db: Session, template_id: str, **kwargs):
    """Update a rubric template."""
    template = db.query(RubricTemplate).filter(RubricTemplate.id == template_id).first()
    if template:
        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)
        template.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(template)
    return template


def delete_rubric_template(db: Session, template_id: str):
    """Delete a rubric template."""
    template = db.query(RubricTemplate).filter(RubricTemplate.id == template_id).first()
    if template:
        db.delete(template)
        db.commit()
    return True


def get_or_create_professor_configuration(db: Session, professor_id: str):
    """Get or create professor configuration - alias for backward compatibility."""
    return get_professor_config(db, professor_id)


def update_professor_configuration(db: Session, professor_id: str, **kwargs):
    """Update professor configuration - alias for backward compatibility."""
    return update_professor_config(db, professor_id, **kwargs)


def get_audit_logs(db: Session, user_id: str = None, limit: int = 100):
    """Get audit logs for a user or all users."""
    query = db.query(AuditLog)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()


def get_grading_statistics(db: Session, professor_id: str = None):
    """Get grading statistics."""
    query = db.query(GradingStatistics)
    if professor_id:
        query = query.filter(GradingStatistics.professor_id == professor_id)
    return query.all()


def create_or_update_statistics(db: Session, professor_id: str, **kwargs):
    """Create or update grading statistics."""
    stats = db.query(GradingStatistics).filter(
        GradingStatistics.professor_id == professor_id
    ).first()
    
    if not stats:
        stats = GradingStatistics(professor_id=professor_id)
        db.add(stats)
    
    for key, value in kwargs.items():
        if hasattr(stats, key):
            setattr(stats, key, value)
    
    db.commit()
    db.refresh(stats)
    return stats

