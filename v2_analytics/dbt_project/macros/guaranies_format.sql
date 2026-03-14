{% macro guaranies_format(column_name) %}
    cast({{ column_name }} as decimal(18,2))
{% endmacro %}
