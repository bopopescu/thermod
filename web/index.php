<?php
	// hostname (or IP address) and port on which Thermod is listening
	$HOST = 'localhost';
	$PORT = '4344';
?>
<!DOCTYPE html>
<html lang="en">
	<head>
		<meta charset="utf-8">
		<title>Thermod Web Manager</title>
		<script language="javascript" type="text/javascript" src="/javascript/jquery/jquery.js"></script>
		<script language="javascript" type="text/javascript" src="/javascript/jquery-ui/jquery-ui.js"></script>
		<link type="text/css" href="/javascript/jquery-ui/css/smoothness/jquery-ui.css" rel="stylesheet" />
		<link type="text/css" href="/javascript/jquery-ui/themes/base/jquery.ui.all.css" rel="stylesheet" />
		<script>
			// thermod settings
			var settings;  

			// map tmax temperature to 'heating on'
			function is_on(temp)
			{
				if(temp == 'tmax')
					return true;
				else
					return false;
			}

			// show spinner for long operations
			function start_loading()
			{
				$('body').addClass('loading');
				$('#spinner-back').addClass('ui-widget-overlay');
			}

			// hide spinner
			function stop_loading()
			{
				$('body').removeClass('loading');
				$('#spinner-back').removeClass('ui-widget-overlay');
			}

			// refresh the selectmenu of target status
			function target_status_refresh()
			{
				$('#target-status option[value=' + settings['status'] + ']').prop('selected', true);

				if($.ui.version >= '1.11')
					$('#target-status').selectmenu('refresh');
			}

			// handle the change event of target status
			function target_status_change(event, ui)
			{
					var target_status = $('#target-status option:selected').prop('value');

					$.post('settings.php', {'host':'<?=$HOST;?>', 'port':'<?=$PORT;?>', 'status': target_status}, function(data)
					{
						if(!('error' in data))
						{
							settings['status'] = target_status;
							get_heating_status_and_refresh();
						}
						else
						{
							var error = (('explain' in data) ? data['explain'] : data['error']);
							$("#dialog").dialog('option', 'title', 'Cannot change status');
							$("#dialog").dialog('option', 'buttons', {'Close': function() { $(this).dialog('close'); }});
							$("#dialog").html('<p><span class="ui-icon ui-icon-alert" style="float: left; margin: 0.3ex 1ex 7ex 0;"></span>Cannot change status: <em>&quot;' + error + '&quot;</em>.</p>');

							stop_loading();
							$("#dialog").dialog('open');
							target_status_refresh();
						}
					},'json');

			}

			// retrieve heating status from daemon and refresh header web page
			function get_heating_status_and_refresh()
			{
				$.get('status.php', {'host':'<?=$HOST;?>', 'port':'<?=$PORT;?>'}, function(data)
				{
					if(!('error' in data))
					{
						var curr = data['temperature'];
						var target = data['target'];
						
						$('#current-status').prop('value', (data['status']==1 ? 'On' : 'Off'));
						$('#current-temperature').prop('value', data['temperature'].toFixed(2));
						$('#target-temperature').prop('value', (data['target'] ? data['target'].toFixed(2) : 'n.a.'));
					}
					else
					{
						stop_loading();
						$('#current-status').prop('value', 'n.a.');
						$('#current-temperature').prop('value', 'n.a.');
						$('#target-temperature').prop('value', 'n.a.');
					}
				},'json');
			}

			// handle 'slide' event of slider
			function slider_slide(event, ui)
			{
				var precision;
				var tname = $(this).attr('id').substr(7);

				switch(tname)
				{
					case 'grace-time':
						precision = 0;
						break;
					
					default:
						precision = 1;
				}

				$('#' + tname).prop('value', ui.value.toFixed(precision));
			}

			// handle 'change' event of slider
			function slider_change(event, ui)
			{
				var tname = $(this).attr('id').substr(7);

				switch(tname)
				{
					case 'tmax':
					case 'tmin':
					case 't0':
						settings['temperatures'][tname] = ui.value;
						break;

					case 'grace-time':
						if(ui.value == 0)
							settings['grace_time'] = null;
						else
							settings['grace_time'] = ui.value * 60;
						break;

					case 'differential':
						settings['differential'] = ui.value;
						break;
				}
			}

			$(function()
			{
				// main objects of the page
				if($.ui.version >= '1.11')
					$('#target-status').selectmenu({change: target_status_change});
				else
					$('#target-status').change(target_status_change);

				$('#tabs').tabs();
				$('#days').buttonset();
				$('.hour').button({disabled: true});
				$('.quarter').button({disabled: true});

				$('.tslider').slider(
				{
					range: 'min',
					min: 0.0,
					max: 30.0,
					step: 0.1,
					slide: slider_slide,
					change: slider_change
				});

				$('.dslider').slider(
				{
					range: 'min',
					min: 0.0,
					max: 1.0,
					step: 0.1,
					slide: slider_slide,
					change: slider_change
				});

				$('.gslider').slider(
				{
					range: 'min',
					min: 0,
					max: 120,
					step: 5,
					slide: slider_slide,
					change: slider_change
				});

				$('.slider-input').change(function()
				{
					var name = $(this).prop('name');
					var temp = $(this).prop('value');

					$('#slider-' + name).slider('option', 'value', temp);
				});
				
				$('#save').button({disabled: true});

				$("#dialog").dialog(
				{
					autoOpen: false,
					modal: true,
					resizable: false,
					minWidth: 370,
					closeOnEscape: true
				});

				// bind events
				$('#days input').change(function()
				{
					$('#save').button('option', 'disabled', false);

					var day = $(this).prop('value');
					for(var hour in settings['timetable'][day])
					{
						$('#' + hour).button('option', 'disabled', false);
						
						for(quarter=0; quarter<4; quarter++)
						{
							$('#' + hour + 'q' + quarter).button('option', 'disabled', false);
							$('#' + hour + 'q' + quarter).prop('checked',is_on(settings['timetable'][day][hour][quarter])).change();
						}
					}
				});

				$('.hour').click(function(event)
				{
					var day = $('#days input:checked').prop('value');
					var hour = $(this).prop('name');
					var checked = $(this).prop('checked');

					for(quarter=0; quarter<4; quarter++)
					{
						$('#' + hour + 'q' + quarter).prop('checked',checked).button('refresh');
						settings['timetable'][day][hour][quarter] = (checked ? 'tmax' : 'tmin');
					}
				});

				$('.quarter').change(function()
				{
					var day = $('#days input:checked').prop('value');
					var hour = $(this).prop('name').substr(0,3);
					var quarter = $(this).prop('name').substr(4,1);
					var checked = false;

					if($(this).prop('checked'))
						checked = true;
					else
						if($('#' + hour + 'q0').prop('checked')
								|| $('#' + hour + 'q1').prop('checked')
								|| $('#' + hour + 'q2').prop('checked')
								|| $('#' + hour + 'q3').prop('checked'))
							checked = true;

					$('#' + hour).prop('checked', checked).button('refresh');
				});

				$('.quarter').click(function()
				{
					var day = $('#days input:checked').prop('value');
					var hour = $(this).prop('name').substr(0,3);
					var quarter = $(this).prop('name').substr(4,1);
					settings['timetable'][day][hour][quarter] = ($(this).prop('checked') ? 'tmax' : 'tmin');
				});

				$('#save').click(function()
				{
					$.post('settings.php', {'host':'<?=$HOST;?>', 'port':'<?=$PORT;?>', 'settings': settings}, function(data)
					{
						if(!('error' in data))
						{
							$("#dialog").dialog('option', 'title', 'Settings saved');
							$("#dialog").dialog('option', 'buttons', {'Ok': function() { $(this).dialog('close'); }});
							$("#dialog").html('<p><span class="ui-icon ui-icon-circle-check" style="float: left; margin: 0.3ex 1ex 2ex 0;"></span>New settings correctly saved!</p>');
							get_heating_status_and_refresh();
						}
						else
						{
							$("#dialog").dialog('option', 'title', 'Cannot save settings');
							$("#dialog").dialog('option', 'buttons', {'Close': function() { $(this).dialog('close'); }});
							$("#dialog").html('<p><span class="ui-icon ui-icon-alert" style="float: left; margin: 0.3ex 1ex 7ex 0;"></span>Cannot save new settings, this is the reported error: <em>&quot;' + data['error'] + '&quot;</em>.</p>');

							// TODO forse il dialog di OK si può non mostrare e mostrare solo quello di errore
							//stop_loading();
							//$("#dialog").dialog('open');
						}

						stop_loading();
						$("#dialog").dialog('open');
					},'json');
				});

				// settings initialization
				get_heating_status_and_refresh();
				
				$.get('settings.php', {'host':'<?=$HOST;?>', 'port':'<?=$PORT;?>'}, function(data)
				{
					if(!('error' in data))
					{
						settings = data;
						target_status_refresh();
						$('#<?=strtolower(date('l'));?>').prop('checked', true).change();

						$('#tmax').prop('value', settings['temperatures']['tmax'].toFixed(1));
						$('#tmin').prop('value', settings['temperatures']['tmin'].toFixed(1));
						$('#t0').prop('value', settings['temperatures']['t0'].toFixed(1));
						$('#differential').prop('value', settings['differential'].toFixed(1));

						$('#slider-tmax').slider('option', 'value', settings['temperatures']['tmax']);
						$('#slider-tmin').slider('option', 'value', settings['temperatures']['tmin']);
						$('#slider-t0').slider('option', 'value', settings['temperatures']['t0']);
						$('#slider-differential').slider('option', 'value', settings['differential']);

						var grace = settings['grace_time'] ? settings['grace_time']/60 : 0;
						$('#grace-time').prop('value', grace.toFixed(0));
						$('#slider-grace-time').slider('option', 'value', grace);
					}
					else
					{
						stop_loading();
						$('#days').buttonset('option', 'disabled', true);
						$("#dialog").dialog('option', 'title','Error');
						$("#dialog").dialog('option', 'buttons', {'Close': function() { $(this).dialog('close'); }});
						$("#dialog").html('<p><span class="ui-icon ui-icon-alert" style="float: left; margin: 0.3ex 1ex 7ex 0;"></span>Cannot retrieve data from Thermod, this is the reported error: <em>&quot;' + data['error'] + '&quot;</em>.</p>');
						$("#dialog").dialog('open');
					}
				},'json');
			});

			$(document).ajaxStart(start_loading).ajaxStop(stop_loading);
		</script>
		<style>
			/* global */
			#spinner { display: none; }
			#spinner-img
			{
				position: fixed;
				z-index: 1000;
				top: 0;
				left: 0;
				height: 100%;
				width: 100%;
				background: url('css/images/spinner.gif') 50% 50% no-repeat;
				/*opacity: .8;
				filter: Alpha(Opacity=80); /* support: IE8 */
			}
			
			body.loading { overflow: hidden; }
			body.loading #spinner { display: block; }
			
			.clearer { clear: both; }
			
			/* header */
			#main { font-size: 90%; }
			#main ul { list-style-type: none; }
			#main ul li { display: block; float: left; text-align: center; width: 10em; margin-bottom: 1em; }
			#main ul li input { cursor: default; }
			
			#target-status { width: 9.8em; }
			#target-status-button { margin-top: 0.3ex; }
			#current-status { width: 4em; margin-top: 0.3ex; }
			#current-temperature { width: 4em; margin-top: 0.3ex; }
			#target-temperature { width: 4em; margin-top: 0.3ex; }
			
			#tabs { font-size: 90%; margin-top: 1em; }
			
			/* schedule */
			#schedule p { margin: 0px 0px 1ex 0px; }
			#days { margin-bottom: 3ex; }
			#hours { margin-bottom: 1.5ex; }
			.hour-box { float: left; text-align: center; margin-bottom: 1.5ex; width: 4.8em; }
			.quarters-box { font-size: 58%; margin: 0.2ex; }
			
			/* settings */
			.slider-container { clear: both; padding-bottom: 5ex; margin-left: 1em; }
			.slider-label { float: left; width: 9ex; text-align: right; margin: 0px 1ex 0px 0px; }
			.slider-input { float: left; text-align: center; }
			.tslider, .dslider, .gslider { float: left; min-width: 100px; max-width: 400px; margin: 0.5ex 2ex 0px 2ex; } /* TODO cercare di disegnare la slider alla massima lunghezza possibile */
			
			
			/* save */
			#buttons { font-size: 90%; padding: 1em 1.4em; background: #eee; margin-top: 1em; }
			#buttons p { margin: 0px 0px 1ex 0px; }
		</style>
	</head>
	<body>
		<h1>Thermod Web Manager</h1>
		<div id="main" class="ui-widget-header ui-corner-all">
			<ul>
				<li>
					<label for="target-status">Status</label>
					<select id="target-status" name="target-status">
						<!-- TODO t_max e t_min non hanno il pedice!! -->
						<option value="auto">Auto</option>
						<option value="tmax">T<small><sub>max</sub></small></option>
						<option value="tmin">T<small><sub>min</sub></small></option>
						<option value="t0">Antifreeze</option>
						<option value="off">Off</option>
					</select>
				</li>
				<li>
					<label for="current-status">Heating</label>
					<input id="current-status" class="ui-widget ui-button ui-corner-all ui-state-default" type="text" value="" readonly="readonly" />
				</li>
				<li>
					<label for="current-temperature">Curr. Temp.</label>
					<input id="current-temperature" class="ui-widget ui-button ui-corner-all ui-state-default" type="text" value="" readonly="readonly" />
				</li>
				<li>
					<label for="target-temperature">Target Temp.</label>
					<input id="target-temperature" class="ui-widget ui-button ui-corner-all ui-state-default" type="text" value="" readonly="readonly" />
				</li>
			</ul>
			<div class="clearer"></div>
		</div>

		<div id="dialog"></div>
		<div id="spinner">
			<div id="spinner-img"></div>
			<div id="spinner-back" class="ui-front"></div>
		</div>

		<div id="tabs">
			<ul>
				<li><a href="#schedule">Schedule</a></li>
				<li><a href="#settings">Settings</a></li>
			</ul>

			<div id="schedule">
				<p>Select day</p>
				<div id="days">
					<input type="radio" name="day" id="monday" value="monday" /><label for="monday">Monday</label>
					<input type="radio" name="day" id="tuesday" value="tuesday" /><label for="tuesday">Tuesday</label>
					<input type="radio" name="day" id="wednesday" value="wednesday" /><label for="wednesday">Wednesday</label>
					<input type="radio" name="day" id="thursday" value="thursday" /><label for="thursday">Thursday</label>
					<input type="radio" name="day" id="friday" value="friday" /><label for="friday">Friday</label>
					<input type="radio" name="day" id="saturday" value="saturday" /><label for="saturday">Saturday</label>
					<input type="radio" name="day" id="sunday" value="sunday" /><label for="sunday">Sunday</label>
				</div>

				<div id="hours">
					<p>Select switch-on hours</p>
					<?php for($i=0; $i<24; $i++): ?>
						<div class="hour-box">
							<?php $h = sprintf('%02d',$i); ?>
							<input type="checkbox" class="hour" id="h<?=$h?>" name="h<?=$h?>" /><label for="h<?=$h?>"><?=$h?>:--</label>
							<div class="quarters-box">
								<input type="checkbox" class="quarter" id="h<?=$h?>q0" name="h<?=$h?>q0" value="1" /><label for="h<?=$h?>q0">00</label>
								<input type="checkbox" class="quarter" id="h<?=$h?>q1" name="h<?=$h?>q1" value="1" /><label for="h<?=$h?>q1">15</label>
								<input type="checkbox" class="quarter" id="h<?=$h?>q2" name="h<?=$h?>q2" value="1" /><label for="h<?=$h?>q2">30</label>
								<input type="checkbox" class="quarter" id="h<?=$h?>q3" name="h<?=$h?>q3" value="1" /><label for="h<?=$h?>q3">45</label>
							</div>
						</div>
					<?php endfor; ?>
					<div class="clearer"></div>
				</div>

				<!--div id="buttons">
					<p>Save settings</p>
					<form action="?">
					<input type="button" id="save" value="Save" />
				</div-->
			</div>

			<div id="settings">
				<p>Set temperatures</p>
				<div class="slider-container">
					<label class="slider-label" for="tmax">Max</label>
					<input class="slider-input" type="text" id="tmax" name="tmax" size="5" />
					<div class="tslider" id="slider-tmax"></div>
				</div>
				
				<div class="slider-container">
					<label class="slider-label" for="tmin">Min</label>
					<input class="slider-input" type="text" id="tmin" name="tmin" size="5" />
					<div class="tslider" id="slider-tmin"></div>
				</div>
				
				<div class="slider-container">
					<label class="slider-label" for="t0">Antifreeze</label>
					<input class="slider-input" type="text" id="t0" name="t0" size="5" />
					<div class="tslider" id="slider-t0"></div>
				</div>
				
				<p>Set other settings</p>
				
				<div class="slider-container">
					<label class="slider-label" for="differential">Differential</label>
					<input class="slider-input" type="text" id="differential" name="differential" size="5" />
					<div class="dslider" id="slider-differential"></div>
				</div>
				
				<div class="slider-container">
					<label class="slider-label" for="grace-time">Grace time</label>
					<input class="slider-input" type="text" id="grace-time" name="grace-time" size="5" />
					<div class="gslider" id="slider-grace-time"></div>
				</div>
			</div>
		</div>

		<div id="buttons" class="ui-widget ui-widget-content ui-corner-all">
			<p>Save settings</p>
			<input type="button" id="save" value="Save" />
		</div>
	</body>
</html>
