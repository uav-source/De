import xml.etree.ElementTree as ET

from scripts.package_full_project import M_NS, omml_to_text


def test_omml_fraction_and_subscript_render_as_readable_text():
    formula = ET.fromstring(
        f"""
        <m:oMath xmlns:m="{M_NS}">
          <m:f>
            <m:num><m:r><m:t>a</m:t></m:r></m:num>
            <m:den>
              <m:sSub>
                <m:e><m:r><m:t>b</m:t></m:r></m:e>
                <m:sub><m:r><m:t>k</m:t></m:r></m:sub>
              </m:sSub>
            </m:den>
          </m:f>
        </m:oMath>
        """
    )

    assert omml_to_text(formula) == "(a)/(b_{k})"


def test_omml_delimiter_preserves_configured_brackets():
    formula = ET.fromstring(
        f"""
        <m:oMath xmlns:m="{M_NS}">
          <m:d>
            <m:dPr>
              <m:begChr m:val="["/>
              <m:endChr m:val="]"/>
            </m:dPr>
            <m:e><m:r><m:t>x</m:t></m:r></m:e>
          </m:d>
        </m:oMath>
        """
    )

    assert omml_to_text(formula) == "[x]"
