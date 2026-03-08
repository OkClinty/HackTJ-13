var get_data_area = function () {
    return $("#data_area");
}

var get_python_output_area = function () {
    return $("#python_output");
}

var get_python_output_graph = function () {
    return $("#python_output_graph");
}

/* More about syntax: http://www.graphviz.org/doc/info/lang.html */
var parse = function () {
    var description = get_data_area().val();
    if (typeof (description) == "undefined" ||
        description === "")
        return undefined;
    var lines = description.split("\n");
    var result = [];
    var directed = $("#graph_type").val() === "digraph";
    var sep = directed ? "->" : "--";
    var ignore_the_first_line = $("#first_line_checkbox").is(":checked");

    for (var i in lines) {
        if (ignore_the_first_line) {
            ignore_the_first_line = false;
            continue;
        }
        var line = lines[i].trim();
        if (line.length < 1 || line[0] === "#") {
            continue;
        }
        var elems = line.split(/\s+/);
        if (elems.length !== 3)
            return undefined;

        var from = elems[0];
        var to = elems[1];
        var weight = Number(elems[2]);
        if (Number.isNaN(weight))
            return undefined;

        var edge = from + sep + to + "[label=\"" + elems[2] + "\"]";
        result.push(edge);
    }
    return (directed ? "digraph" : "graph") + "{" + result.join(";") + "}";
}

/* Query example: https://draw.khairulin.com/chart?cht=gv&chl=digraph{1->2;2->3;1->3;3->4;1->5} */
var render_service = "https://draw.khairulin.com/";
var previous_graph = "";

var chart_url = function (graph) {
    return render_service + "chart?cht=gv&chl=" + encodeURIComponent(graph);
}

var clear_error = function () {
    var small = $("#error_message");
    small.html("")
    small.removeClass("error");
}

var report_error = function (message) {
    var small = $("#error_message");
    small.html(message);
    small.addClass("error");
}

var render_chart = function (graph) {
    if (graph !== previous_graph) {
        history.pushState({query: "graph"}, "graphpage", "?q=" + graph);
        $("#output").attr("src", chart_url(graph));
        previous_graph = graph;
    }
}

var set_python_output = function (message, isError) {
    var outputArea = get_python_output_area();
    outputArea.text(message);
    if (isError) {
        outputArea.removeClass("text-slate-700").addClass("text-red-700");
    } else {
        outputArea.removeClass("text-red-700").addClass("text-slate-700");
    }
}

var set_python_output_graph = function (graphDot) {
    var graphImage = get_python_output_graph();
    if (!graphDot) {
        graphImage.addClass("hidden");
        graphImage.attr("src", "");
        return;
    }
    graphImage.attr("src", chart_url(graphDot));
    graphImage.removeClass("hidden");
}

var optimized_result_to_dot = function (result) {
    if (!result || !Array.isArray(result.edges) || result.edges.length === 0)
        return "";

    var dotEdges = [];
    for (var i = 0; i < result.edges.length; i++) {
        var edge = result.edges[i];
        if (!edge || !edge.source || !edge.target)
            continue;

        var style = edge.selected ? "color=\"#16a34a\",penwidth=3" : "color=\"#94a3b8\",style=\"dashed\"";
        var label = "label=\"" + edge.weight + "\"";
        dotEdges.push("\"" + edge.source + "\"->\"" + edge.target + "\"[" + label + "," + style + "]");
    }

    if (dotEdges.length === 0)
        return "";

    return "digraph{rankdir=LR;" + dotEdges.join(";") + "}";
}

var summary_from_result = function (result) {
    var summary = (result && result.summary) ? result.summary : {};
    var cost = (typeof summary.assignment_cost === "number") ? summary.assignment_cost : null;
    var feasible = !!summary.feasible;
    var assignment = summary.assignment_map ? JSON.stringify(summary.assignment_map, null, 2) : "{}";
    var lines = [
        "Optimization complete",
        "Feasible: " + feasible
    ];
    if (cost !== null) {
        lines.push("Assignment cost: " + cost);
    }
    lines.push("Assignment map:\n" + assignment);
    return lines.join("\n");
}

var execute_python = async function (edgesText) {
    try {
        set_python_output("Running Python...", false);
        set_python_output_graph("");
        var response = await fetch("/api/process-edges", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({edges_text: edgesText})
        });

        var payload = await response.json();
        if (!response.ok || !payload.ok) {
            var message = (payload && payload.error) ? payload.error : "Python processing failed.";
            set_python_output_graph("");
            set_python_output(message, true);
            return;
        }

        var optimizedDot = optimized_result_to_dot(payload.result);
        set_python_output_graph(optimizedDot);
        set_python_output(summary_from_result(payload.result), false);
    } catch (error) {
        set_python_output_graph("");
        set_python_output("Unable to reach the Python endpoint.", true);
    }
}

var show = async function () {
    clear_error();
    var graph = parse();
    var inputText = get_data_area().val();

    if (graph)
        render_chart(graph);
    else {
        report_error("unable to parse data (use: from to weight)");
        set_python_output_graph("");
        set_python_output("Fix the input format, then click Draw again.", true);
        return;
    }

    await execute_python(inputText);
}

var parse_url_query = function () {
    var url = window.location.href;
    var hash = url.indexOf("#");
    if (hash >= 0)
        url = url.substr(0, hash);
    var qmark = url.indexOf("?");
    if (qmark < 0)
        return "";
    var args = decodeURI(url.substr(qmark + 1)).split("&");
    for (var i in args) {
        var pair = args[i].split("=");
        if (pair.length >= 2 && pair[0] === "q")
            return pair.slice(1).join("=");
    }
    return "";
}

var handle_query = function () {
    var query = parse_url_query();
    if (query.length > 0 && query[query.length - 1] === "}") {
        var graph_type = "";
        var data = "";
        if (query.substr(0, 6) === "graph{") {
            graph_type = "graph";
            data = query.substr(6, query.length - 7);
        } else if (query.substr(0, 8) === "digraph{") {
            graph_type = "digraph";
            data = query.substr(8, query.length - 9);
        } else {
            return;
        }
        $("#graph_type").val(graph_type);
        var separator = graph_type === "graph" ? "--" : "->";
        var edges = data.split(";");
        var lines = [];
        for (var i in edges) {
            var e = edges[i];
            if (e.length < 1)
                continue;
            var sep = e.indexOf(separator);
            if (sep < 1)
                continue;

            var from = e.substr(0, sep).trim();
            var brace = e.indexOf("[", sep + 2);
            var to = "";
            var weight = "";

            if (brace < 0) {
                continue;
            }

            to = e.substr(sep + 2, brace - sep - 2).trim();
            var labelMatch = e.match(/label="([^"]+)"/);
            if (!labelMatch || labelMatch.length < 2) {
                continue;
            }
            weight = labelMatch[1].trim();
            lines.push(from + " " + to + " " + weight);
        }
        if (lines.length > 0) {
            get_data_area().val(lines.join("\n"));
            show();
        }
    }
}

var on_copy_button_click = function () {
    var data_area = get_data_area().get(0);
    data_area.select();
    data_area.setSelectionRange(0, 99999); /*For mobile devices*/
    document.execCommand("copy");
}

$(document).ready(function () {
    $("#show_button").click(function () {
        show();
    });
    $("#copy_button").click(on_copy_button_click);
    shortcut.add("Ctrl+Enter", show);
    handle_query();
});
