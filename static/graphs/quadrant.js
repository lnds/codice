var dhs = document.getElementById("quadrant");
var w = dhs.offsetWidth;
var h = w;
var dqs = document.getElementById("quadrant-scatter");
dqs.setAttribute('width', w);
dqs.setAttribute('height', h);
var svg = d3.select("#quadrant-scatter"),
    margin = {top: 0, right: 0, bottom: 0, left: 0},
    width = +svg.attr("width"),
    height = +svg.attr("height"),
    domainwidth = width - margin.left - margin.right,
    domainheight = height  - margin.top - margin.bottom;

var x = d3.scale.linear()
    .domain(padExtent([1.0, 0], 0))
    .range(padExtent([0, domainwidth]));
var y = d3.scale.linear()
    .domain(padExtent([0, 1.0], 0))
    .range(padExtent([domainheight, 0]));

var g = svg.append("g")
		.attr("transform", "translate(" + margin.top + "," + margin.left + ")");

var ww = width - margin.left - margin.right;
var hh = height - margin.top - margin.bottom;
g.append("rect")
    .attr("width", ww)
    .attr("height", hh)
    .attr("fill", "#F6F6F6");

var r2 = Math.sqrt(2.0);
var ra = 0.75 * r2;
var rb = 0.50 * r2;
var rc = 0.25 * r2;


g.append("clipPath")
    .attr("id", "ra_ellipse-clip")
    .append("ellipse")
    .attr("cx", 0)
    .attr("cy", hh)
    .attr("rx", ra*ww)
    .attr("ry", ra*hh);

g.append("rect")
    .attr("clip-path", "url(#ra_ellipse-clip)")
    .attr("width", ww)
    .attr("height", hh)
    .attr("fill", "#c9dec1");


g.append("clipPath")
    .attr("id", "rb_ellipse-clip")
    .append("ellipse")
    .attr("cx", 0)
    .attr("cy", hh)
    .attr("rx", rb*ww)
    .attr("ry", rb*hh);

g.append("rect")
    .attr("clip-path", "url(#rb_ellipse-clip)")
    .attr("width", ww*rb)
    .attr("height", hh)
    .attr("fill", "#7fadde");


g.append("clipPath")
    .attr("id", "rc_ellipse-clip")
    .append("ellipse")
    .attr("cx", 0)
    .attr("cy", hh)
    .attr("rx", rc*ww)
    .attr("ry", rc*hh);

g.append("rect")
    .attr("clip-path", "url(#rc_ellipse-clip)")
    .attr("width", ww*rc)
    .attr("height", hh)
    .attr("fill", "#deaa8c");


function show_quadrant(data) {

    data.forEach(function (d) {
        d.cx = +d.cx;
        d.cy = +d.cy;
    });

    var div = d3.select("body").append("div")
        .attr("class", "quadrant_tooltip")
        .style("opacity", 0);

    var node = g.selectAll("circle")
        .data(data)
        .enter().append("circle")
        .attr("class", "dot")
        .attr("r", function (d) {
            return Math.max(7, d.size / 25);
        })
        .attr("cx", function (d) {
            return x(d.x);
        })
        .attr("cy", function (d) {
            return y(d.y);
        })
         .style("fill", function (d) {
            return "rgb(" + d.weight2 * 255 + "," + d.weight1 * 255 + "," + d.weight1 * 32 + ")";

        })
        .on("mouseover", function (d, i) {
            var radius = Math.max(7, d.size / 25);
            d3.select(this).attr({
                r: radius * 2
            });
            div.transition()
                .duration(200)
                .style("opacity", .9);
            div.html("<span> " + d.developer
                + " </span>"
                + "<br>cx:" + d.x + " cy:" + d.y
                + "<br>impact:" + Math.round(d.impact)
                + "<br>Thpt:" + Math.round(d.weight1 * 100.0)
                + "<br>Chrn:" + Math.round(d.weight2 * 100.0))
                .style("left", (d3.event.pageX) + "px")
                .style("top", (d3.event.pageY - 28) + "px");

        })
        .on("mouseout", function (d, i) {
            var radius = Math.max(7, d.size / 25);
            d3.select(this).attr({
                r: radius
            });
            div.transition()
                .duration(500)
                .style("opacity", 0);
        })
        .on("click", function (d) {
            if (d.repo_id > 0) {
                window.location.href = '/devs/r/' + d.repo_id + "/profile/" + d.developer_id;
            } else {
                window.location.href = '/devs/profile/' + d.developer_id;
            }
        })
       ;


    g.append("g")
      .attr("class", "x axis")
      .attr("transform", "translate(0," + y.range()[0] / 2 + ")")
      .call(d3.svg.axis().scale(x).orient("bottom").ticks(0));

    g.append("g")
      .attr("class", "y axis")
      .attr("transform", "translate(" + x.range()[1] / 2 + ", 0)")
      .call(d3.svg.axis().scale(y).orient("left").ticks(0));

}

function padExtent(e, p) {
  	if (p === undefined) p = 1;
  	return ([e[0] - p, e[1] + p]);
}

show_quadrant(v_quadrant_data);