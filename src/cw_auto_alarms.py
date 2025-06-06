import logging

from actions import check_alarm_tag, process_alarm_tags, delete_alarms, process_lambda_alarms, \
    scan_and_process_alarm_tags, process_rds_alarms, separate_wildcard_alarms, get_active_accounts_by_organizational_unit
from os import getenv

def lambda_handler(event, context):
    logger = logging.getLogger()
    log_level = getenv("LOGLEVEL", "INFO")
    level = logging.getLevelName(log_level)
    logger.setLevel(level)

    create_alarm_tag = getenv("ALARM_TAG", "Create_Auto_Alarms")

    target_org_units = getenv("TARGET_ORG_UNITS", "")
    target_org_units = target_org_units.split(",")

    target_regions = getenv("TARGET_REGIONS", "")
    target_regions = target_regions.split(",")

    local_account_id = getenv("LOCAL_ACCOUNT_ID", None)

    org_mgmt_account_id = getenv("ORG_MGMT_ACCOUNT", None)

    cw_namespace = getenv("CLOUDWATCH_NAMESPACE", "CWAgent")

    create_default_alarms_flag = getenv("CREATE_DEFAULT_ALARMS", "true").lower()

    append_dimensions = getenv("CLOUDWATCH_APPEND_DIMENSIONS", 'InstanceId, ImageId, InstanceType')
    append_dimensions = [dimension.strip() for dimension in append_dimensions.split(',')]

    alarm_cpu_high_default_threshold = getenv("ALARM_CPU_HIGH_THRESHOLD", "75")
    alarm_cpu_high_anomaly_detection_default_threshold = getenv("ALARM_DEFAULT_ANOMALY_THRESHOLD", "2")
    alarm_memory_high_default_threshold = getenv("ALARM_MEMORY_HIGH_THRESHOLD", "75")
    alarm_disk_space_percent_free_threshold = getenv("ALARM_DISK_PERCENT_LOW_THRESHOLD", "20")
    alarm_disk_used_percent_threshold = 100 - int(alarm_disk_space_percent_free_threshold)

    alarm_rds_cpu_high_default_threshold = getenv("ALARM_RDS_CPU_HIGH_THRESHOLD", "75")

    alarm_lambda_error_threshold = getenv("ALARM_LAMBDA_ERROR_THRESHOLD", "1")
    alarm_lambda_throttles_threshold = getenv("ALARM_LAMBDA_THROTTLE_THRESHOLD", "1")
    alarm_lambda_dead_letter_error_threshold = getenv("ALARM_LAMBDA_DEAD_LETTER_ERROR_THRESHOLD", "1")
    alarm_lambda_destination_delivery_failure_threshold = getenv("ALARM_LAMBDA_DESTINATION_DELIVERY_FAILURE_THRESHOLD", "1")

    alarm_separator = '-'
    alarm_identifier = getenv("ALARM_IDENTIFIER_PREFIX", 'AutoAlarm')

    default_period = '5m'
    default_evaluation_periods = '1'
    default_statistic = 'Average'

    metric_dimensions_map = {
        cw_namespace: append_dimensions,
        'AWS/EC2': ['InstanceId']
    }
    if 'AutoScalingGroupName' not in metric_dimensions_map[cw_namespace]:
        metric_dimensions_map[cw_namespace].append('AutoScalingGroupName')

    # For Redhat, the default device is xvda2, xfs, for Ubuntu, the default fstype is ext4,
    # for Amazon Linux, the default device is xvda1, xfs
    default_alarms = {
        # default<number> added to the end of the key to  make the key unique
        # this differentiate alarms with similar settings but different thresholds
        'AWS/RDS': [
            {
                'Key': alarm_separator.join(
                    [alarm_identifier, 'AWS/RDS', 'CPUUtilization', 'GreaterThanThreshold', default_period,
                     default_evaluation_periods, default_statistic, 'Created_by_CloudWatchAutoAlarms']),
                'Value': alarm_rds_cpu_high_default_threshold
            }
        ],
        'AWS/EC2': [
            {
                'Key': alarm_separator.join(
                    [alarm_identifier, 'AWS/EC2', 'CPUUtilization', 'GreaterThanThreshold', default_period,
                     default_evaluation_periods, default_statistic, 'Created_by_CloudWatchAutoAlarms']),
                'Value': alarm_cpu_high_default_threshold
            },
            # This is an example alarm using anomaly detection
            # {
            #     'Key': alarm_separator.join(
            #         [alarm_identifier, 'AWS/EC2', 'CPUUtilization', 'GreaterThanUpperThreshold', default_period,
            #          default_evaluation_periods, default_statistic, 'Created_by_CloudWatchAutoAlarms']),
            #     'Value': alarm_cpu_high_anomaly_detection_default_threshold
            # }
        ],
        'AWS/Lambda': [
            {
                'Key': alarm_separator.join(
                    [alarm_identifier, 'AWS/Lambda', 'Errors', 'GreaterThanThreshold', default_period,
                     default_evaluation_periods, default_statistic, 'Created_by_CloudWatchAutoAlarms']),
                'Value': alarm_lambda_error_threshold
            },
            {
                'Key': alarm_separator.join(
                    [alarm_identifier, 'AWS/Lambda', 'Throttles', 'GreaterThanThreshold', default_period,
                     default_evaluation_periods, default_statistic, 'Created_by_CloudWatchAutoAlarms']),
                'Value': alarm_lambda_throttles_threshold
            }
        ],
        cw_namespace: {
            'Windows': [

                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'LogicalDisk % Free Space', 'objectname', 'LogicalDisk',
                         'instance', 'C:', 'LessThanThreshold', default_period, default_evaluation_periods,
                         default_statistic, 'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_disk_space_percent_free_threshold
                },
                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'Memory % Committed Bytes In Use', 'objectname', 'Memory',
                         'GreaterThanThreshold', default_period, default_evaluation_periods, default_statistic,
                         'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_memory_high_default_threshold
                }
            ],
            'Amazon Linux': [
                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'disk_used_percent', 'device', 'nvme0n1p1', 'fstype', 'xfs', 'path',
                         '/', 'GreaterThanThreshold', default_period, default_evaluation_periods, default_statistic,
                         'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_disk_used_percent_threshold
                },
                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'mem_used_percent', 'GreaterThanThreshold', default_period,
                         default_evaluation_periods, default_statistic,
                         'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_memory_high_default_threshold
                }
            ],
            'Red Hat': [
                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'disk_used_percent', 'device', 'xvda2', 'fstype', 'xfs', 'path',
                         '/', 'GreaterThanThreshold', default_period, default_evaluation_periods, default_statistic,
                         'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_disk_used_percent_threshold
                },
                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'mem_used_percent', 'GreaterThanThreshold', default_period,
                         default_evaluation_periods, default_statistic,
                         'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_memory_high_default_threshold
                }
            ],
            'Ubuntu': [
                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'disk_used_percent', 'device', 'xvda1', 'fstype', 'ext4', 'path',
                         '/', 'GreaterThanThreshold', default_period, default_evaluation_periods, default_statistic,
                         'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_disk_used_percent_threshold
                },
                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'mem_used_percent', 'GreaterThanThreshold', default_period,
                         default_evaluation_periods, default_statistic,
                         'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_memory_high_default_threshold
                }
            ],
            'SUSE': [
                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'disk_used_percent', 'device', 'xvda1', 'fstype', 'xfs', 'path',
                         '/', 'GreaterThanThreshold', default_period, default_evaluation_periods, default_statistic,
                         'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_disk_used_percent_threshold
                },
                {
                    'Key': alarm_separator.join(
                        [alarm_identifier, cw_namespace, 'mem_used_percent', 'GreaterThanThreshold', default_period,
                         default_evaluation_periods, default_statistic,
                         'Created_by_CloudWatchAutoAlarms']),
                    'Value': alarm_memory_high_default_threshold
                }
            ]
        }
    }
    logger.info('event received: {}'.format(event))
    event_account_id = event.get('account', None)
    event_region = event.get('region', None)
    if not local_account_id:
        logger.error("Environment variable LOCAL_ACCOUNT_ID is not set")
        raise

    if event_account_id == local_account_id:
        cross_account_id = None
    else:
        cross_account_id = event_account_id

    sns_topic_name = getenv('SNS_TOPIC_NAME')
    sns_topic_account = getenv('SNS_TOPIC_ACCOUNT')

    if not sns_topic_name or not sns_topic_account or not event_region:
        logger.info("SNS_TOPIC_ACCOUNT and SNS_TOPIC_NAME environment variables not set, skipping notifications setup")
        sns_topic_arn = None
    else:
        sns_topic_arn = f"arn:aws:sns:{event_region}:{sns_topic_account}:{sns_topic_name}"


    try:
        if 'source' in event and event['source'] == 'aws.ec2' and event['detail']['state'] == 'running':
            instance_id = event['detail']['instance-id']
            # determine if instance is tagged to create an alarm
            instance_info = check_alarm_tag(instance_id, create_alarm_tag, event_region, cross_account_id)

            # instance has been tagged for alarming, confirm an alarm doesn't already exist
            if instance_info:
                instance_sns_target = [instance_tag['Value'] for instance_tag in instance_info['Tags'] if
                                       instance_tag['Key'] == 'notify']
                if len(instance_sns_target) > 0:
                    target_sns_topic_arn = instance_sns_target[0]
                else:
                    target_sns_topic_arn = sns_topic_arn

                default_filtered_alarms, wildcard_alarms = separate_wildcard_alarms(alarm_separator, cw_namespace, default_alarms)
                process_alarm_tags(instance_id, instance_info, default_filtered_alarms, wildcard_alarms, metric_dimensions_map,
                                   target_sns_topic_arn,
                                   cw_namespace, create_default_alarms_flag, alarm_separator, alarm_identifier, event_region, cross_account_id)
        elif 'source' in event and event['source'] == 'aws.ec2' and event['detail']['state'] == 'terminated':
            instance_id = event['detail']['instance-id']
            result = delete_alarms(instance_id, alarm_identifier, alarm_separator, event_region, cross_account_id)
        elif 'source' in event and event['source'] == 'aws.lambda' and event['detail'][
            'eventName'] == 'TagResource20170331v2':
            logger.debug(
                'Tag Lambda Function event occurred, tags are: {}'.format(event['detail']['requestParameters']['tags']))
            tags = event['detail']['requestParameters']['tags']

            if 'notify' in tags.keys():
                target_sns_topic_arn = tags['notify']
            else:
                target_sns_topic_arn = sns_topic_arn

            function = event['detail']['requestParameters']['resource'].split(":")[-1]
            process_lambda_alarms(function, tags, create_alarm_tag, default_alarms, target_sns_topic_arn,
                                  alarm_separator,
                                  alarm_identifier, event_region, cross_account_id)
        elif 'source' in event and event['source'] == 'aws.lambda' and event['detail'][
            'eventName'] == 'DeleteFunction20150331':
            function = event['detail']['requestParameters']['functionName']
            logger.debug('Delete Lambda Function event occurred for: {}'.format(function))
            delete_alarms(function, alarm_identifier, alarm_separator, event_region, cross_account_id)
        elif 'source' in event and event['source'] == 'aws.rds' and event['detail'].get('eventName',
                                                                                        None) == 'AddTagsToResource':
            logger.info(
                'Tag RDS event occurred, tags are: {}'.format(event['detail']['requestParameters']['tags']))
            tags = event['detail']['requestParameters']['tags']

            instance_sns_target = [tag['value'] for tag in tags if tag.get("key", None) == 'notify']

            if len(instance_sns_target) > 0:
                target_sns_topic_arn = instance_sns_target[0]
            else:
                target_sns_topic_arn = sns_topic_arn

            db_arn = event['detail']['requestParameters']['resourceName']
            if 'cluster' in db_arn:
                is_cluster = True
            else:
                is_cluster = False

            logger.info('Tag DB event occurred for RDS: {}'.format(db_arn))
            process_rds_alarms(db_arn, is_cluster, create_alarm_tag, default_alarms, target_sns_topic_arn,
                               alarm_separator,
                               alarm_identifier, tags, event_region, cross_account_id)
        # Event for RDS database instance deletion:  https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_Events.Messages.html
        elif 'source' in event and event['source'] == 'aws.rds' and 'EventCategories' in event[
            'detail'] and 'deletion' in event['detail']['EventCategories']:
            db_arn = event['detail']['SourceArn']
            db_id = db_arn.split(':')[-1]
            logger.info('Delete DB Instance event occurred for RDS: {}'.format(db_id))
            delete_alarms(db_id, alarm_identifier, alarm_separator, event_region, cross_account_id)
        elif 'action' in event and event['action'] == 'scan':
            logger.debug(
                f'Scanning for EC2 instances with tag: {create_alarm_tag} to create alarm'
            )
            # TODO:  Verify that target_sns_topic_arn is also considered for each instance if set
            if org_mgmt_account_id:
                accounts_by_ou = get_active_accounts_by_organizational_unit(target_org_units, org_mgmt_account_id)
                for ou_id, accounts in accounts_by_ou.items():
                    logger.info(f"Processing Organizational Unit (OU): {ou_id}")
                    for account in accounts:
                        account_id = account['AccountId']
                        account_name = account['AccountName']
                        logger.info(f"Processing account {account_id} ({account_name}) in OU {ou_id}")

                        # Call scan_and_process_alarm_tags for the account
                        for region in target_regions:
                            region = region.strip()
                            logger.info(f"Processing region {region}")
                            # Call scan_and_process_alarm_tags for the account and region
                            scan_and_process_alarm_tags(create_alarm_tag, default_alarms, metric_dimensions_map, sns_topic_arn,
                                                        cw_namespace, create_default_alarms_flag, alarm_separator, alarm_identifier, region, account_id)
            else:
                # Call scan_and_process_alarm_tags for single account
                for region in target_regions:
                    logger.info(f"Processing region {region}")
                    # Call scan_and_process_alarm_tags for the account and region
                    scan_and_process_alarm_tags(create_alarm_tag, default_alarms, metric_dimensions_map, sns_topic_arn,
                                                cw_namespace, create_default_alarms_flag, alarm_separator, alarm_identifier, region)

    except Exception as e:
        # If any other exceptions which we didn't expect are raised
        # then fail the job and log the exception message.
        logger.error('Failure creating alarm: {}'.format(e))
        raise
