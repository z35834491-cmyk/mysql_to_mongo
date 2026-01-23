from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import os
import json
from .models import InspectionConfig, InspectionReport
from .engine import inspection_engine

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def inspection_config(request):
    if request.method == 'GET':
        cfg = InspectionConfig.load()
        return Response({
            "prometheus_url": cfg.prometheus_url,
            "ark_base_url": cfg.ark_base_url,
            "ark_api_key": cfg.ark_api_key,
            "ark_model_id": cfg.ark_model_id
        })
    elif request.method == 'POST':
        data = request.data
        cfg = InspectionConfig.load()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        cfg.save()
        return Response({"msg": "saved"})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def run_inspection(request):
    # Update config if provided
    data = request.data
    if data:
        cfg = InspectionConfig.load()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        cfg.save()
        # Refresh engine config
        inspection_engine.config = cfg
        
    report = inspection_engine.run()
    return Response(report)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_report(request, report_id):
    # Try DB first
    try:
        report = InspectionReport.objects.get(report_id=report_id)
        return Response(report.content)
    except InspectionReport.DoesNotExist:
        # Fallback to file for backward compatibility
        path = f'state/inspection_reports/daily/{report_id}.json'
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return Response(json.load(f))
        return Response({"error": "Report not found"}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def history(request):
    # Get all reports from DB
    reports = InspectionReport.objects.all().order_by('-report_id')
    
    results = []
    for r in reports:
        content = r.content
        risk = content.get('risk_summary', {})
        results.append({
            "report_id": r.report_id,
            "score": 100 - risk.get('score', 0), # Convert risk score to health score
            "summary": content.get('ai_analysis', '')[:100] + '...' if content.get('ai_analysis') else 'No analysis available'
        })
    
    # Handle legacy file items if any
    db_ids = [r.report_id for r in reports]
    path = 'state/inspection_reports/daily'
    if os.path.exists(path):
        for f in os.listdir(path):
            if f.endswith('.json'):
                rid = f.replace('.json', '')
                if rid not in db_ids:
                    with open(os.path.join(path, f), 'r', encoding='utf-8') as f_in:
                        try:
                            content = json.load(f_in)
                            risk = content.get('risk_summary', {})
                            results.append({
                                "report_id": rid,
                                "score": 100 - risk.get('score', 0),
                                "summary": content.get('ai_analysis', '')[:100] + '...' if content.get('ai_analysis') else 'No analysis available'
                            })
                        except:
                            pass
    
    # Sort results by report_id desc
    results.sort(key=lambda x: x['report_id'], reverse=True)
    return Response({"items": results})
