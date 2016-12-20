jQuery(document).ready(function() {    // ECHARTS    require.config({        paths: {            echarts: "/static/peerloan/global/plugins/echarts/"        }    });    // DEMOS    require(        [            'echarts',            'echarts/chart/bar',            'echarts/chart/chord',            'echarts/chart/eventRiver',            'echarts/chart/force',            'echarts/chart/funnel',            'echarts/chart/gauge',            'echarts/chart/heatmap',            'echarts/chart/k',            'echarts/chart/line',            'echarts/chart/map',            'echarts/chart/pie',            'echarts/chart/radar',            'echarts/chart/scatter',            'echarts/chart/tree',            'echarts/chart/treemap',            'echarts/chart/venn',            'echarts/chart/wordCloud'        ],        function(ec) {            //--- BAR ---            var myChart = ec.init(document.getElementById('echarts_bar_receivable'));            var option={			    tooltip : {			        trigger: 'axis',			    },			    xAxis : [			        {			            type : 'category',			            data : []			        }			    ],			    yAxis : [			        {			            type : 'value',			            'name':'Receivable'			        }			    ],			    series : [			        {			            name:'Receivable',			            type:'bar',			            itemStyle: {			                normal: {			                    color: function(params) {			                        // build a color map as your need.			                        var colorList = [			                          '#9BCA63','#9BCA63','#9BCA63','#E87C25','#E87C25','#E87C25'			                            ,'#E87C25','#E87C25','#E87C25','#E87C25','#E87C25'			                        ];			                        return colorList[params.dataIndex]			                    }			                }			            },			            data:[]			        }			    ]			};						$.ajax({				type: "get",				async: false,				url: "/echartsreceivable_list_json",				dataType: "json",				success: function (result) {					if (result) {						var date = [];						var value = [];						for (object in result.data)						{							date.push(result.data[object].date);							value.push(result.data[object].value);						}						option.xAxis[0].data=date;						option.series[0].data=value;						myChart.setOption(option);					}					else {						alert("result not find");					}				},				error: function (errorMsg) {					alert("Error: Loading JSON");				}			});						var myChartbar2 = ec.init(document.getElementById('echarts_bar_investment'));            myChartbar2.setOption({    tooltip : {        trigger: 'axis',    },    xAxis : [        {            type : 'category',            data : ['10/15','11/15','12/15','01/16','02/16','03/16','04/16',                    '05/16','06/16','07/16','08/16']        }    ],    yAxis : [        {            type : 'value',            'name':'Investment'        }    ],    series : [        {            name:'Investment',            type:'bar',        	itemStyle: {	            normal: {	                color: function(params) {	                    // build a color map as your need.	                    var colorList = [	                      '#60C0DD','#60C0DD','#60C0DD','#60C0DD','#60C0DD','#60C0DD',	                        '#60C0DD','#60C0DD','#60C0DD','#60C0DD','#60C0DD'	                    ];	                    return colorList[params.dataIndex]	                }	            }        	},            data:[1000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]        }    ]});myChart.connect([myChartbar2]);myChartbar2.connect([myChart]);            // -- PIE --            var myChart3 = ec.init(document.getElementById('echarts_pie_account'));            var option={        	    title : {			        text: 'Account Balance: $51,100',			        x : 'center',			    },			    tooltip : {			        trigger: 'item',			        formatter: "{a} <br/>{b} : {c} ({d}%)"			    },			    legend: {			        orient : 'vertical',			        x : 'right',			        data:[]			    },			    series : [			        {			            name:'Source',			            type:'pie',			            radius : ['50%', '70%'],			            itemStyle : {			                normal : {			                	color: function(params) {			                        // build a color map as your need.			                        var colorList = [			                           '#27727B','#60C0DD','#FE8463'			                        ];			                        return colorList[params.dataIndex]			                    },			                    label : {			                        show : false			                    },			                    labelLine : {			                        show : false			                    }			                },			                emphasis : {			                    label : {			                        show : true,			                        position : 'center',			                        textStyle : {			                            fontSize : '20',			                            fontWeight : 'bold'			                        }			                    }			                }			            },			            data:[			            ]			        }			    ]            };                        $.ajax({				type: "get",				async: false,				url: "/dashboardpie_list_json",				dataType: "json",				success: function (result) {					if (result) {						var legend_name = [];						var series_data = [];						for (object in result.data)						{							legend_name.push(result.data[object].name);							series_data.push({value:result.data[object].value,name:result.data[object].name});						}						option.legend.data=legend_name;						option.series[0].data=series_data;						myChart3.setOption(option);					}					else {						alert("result not find");					}				},				error: function (errorMsg) {					alert("Error: Loading JSON");				}			});        }    );});